/* USER CODE BEGIN Header */
/**
 ******************************************************************************
 * @file           : main.c
 * @brief          : Main program body
 ******************************************************************************
 * @attention
 *
 * Copyright (c) 2025 STMicroelectronics.
 * All rights reserved.
 *
 * This software is licensed under terms that can be found in the LICENSE file
 * in the root directory of this software component.
 * If no LICENSE file comes with this software, it is provided AS-IS.
 *
 ******************************************************************************
 */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "cmsis_os.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include "oled.h"
#include "telemetry.h"
#include "gyro_safe.h"
#include "stdbool.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <math.h>
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
ADC_HandleTypeDef hadc1;
DMA_HandleTypeDef hdma_adc1;

I2C_HandleTypeDef hi2c2;

TIM_HandleTypeDef htim2;
TIM_HandleTypeDef htim3;
TIM_HandleTypeDef htim4;
TIM_HandleTypeDef htim8;
TIM_HandleTypeDef htim9;
TIM_HandleTypeDef htim12;

UART_HandleTypeDef huart2;
UART_HandleTypeDef huart3;

osThreadId LED_TaskHandle;
osThreadId OLED_TaskHandle;
osThreadId Motor_TaskHandle;
osThreadId Encoder_TaskHandle;
osThreadId Gyro_TaskHandle;
osThreadId Ultrasound_TaskHandle;
osThreadId IR_TaskHandle;
/* USER CODE BEGIN PV */
// osMutexId oledMutexHandle;

volatile float tc1 = 0, tc2 = 0, echo = 0;
// debugging ultrasound
volatile uint32_t echo_debug = 0;
volatile float distance = 0;
volatile float ir_distance_cm = 0.0f;
volatile bool new_measurement_ready = false;
static uint32_t us_cm_hist[3] = {0, 0, 0};
static uint8_t us_cm_hist_idx = 0;
static uint8_t us_cm_hist_count = 0;

// volatile uint8_t obstacle_stop_mode = 0;      // 0=off, 1=on for bare 'F'

// encoder
volatile int delta_a = 0;
volatile int delta_b = 0;

// osMutexId oledMutexHandle;

volatile uint8_t abort_now = 0; // emergency stop, reset

volatile uint8_t rx_byte; // single-byte RX (interrupt)
volatile enum {
  CMD_NONE,
  CMD_FORWARD,
  CMD_REVERSE,
  CMD_STOP,
  CMD_ARC_RIGHT,
  CMD_ARC_LEFT,
  CMD_ARC_RIGHT_REV,
  CMD_ARC_LEFT_REV
} uart_cmd;

static char cmd_buf[256]; // cmd buffer length
static uint8_t cmd_idx = 0;
static char pending_cmd_buf[256];
static volatile uint8_t pending_cmd_ready = 0U;

volatile uint32_t next_start_tick = 0; // when we’re allowed to start the next cmd

/* -------- Script command queue -------- */
typedef enum
{
  SCMD_NONE = 0,
  SCMD_FWD_CM, // value = centimeters (positive)
  SCMD_REV_CM, // value = centimeters (positive)
  SCMD_ARC_FR, // value = degrees  (90..360)
  SCMD_ARC_FL,
  SCMD_ARC_RR,
  SCMD_ARC_RL,
  SCMD_SLIDE_R, // first obstacle
  SCMD_SLIDE_L, // first obstacle
  SCMD_STOP,
  SCMD_EOS,
  SCMD_FIR, // forward infra right
  SCMD_FIL, // forward infra left
  SCMD_FIRO,
  SCMD_FILO,
  SCMD_FU, // forward forever until ultrasound <= threshold
  SCMD_FX  // same as FU but no reverse on overshoot
} script_cmd_t;

typedef struct
{
  script_cmd_t type;
  int value; // deg or cm depending on type
} script_item_t;

#define CMDQ_CAP 32 // max number of commands i set to 15 (16-1)
static volatile script_item_t cmdq[CMDQ_CAP];
static volatile uint8_t q_head = 0, q_tail = 0;

static inline int cmdq_empty(void) { return q_head == q_tail; }
static inline int cmdq_full(void) { return (uint8_t)(q_tail + 1) % CMDQ_CAP == q_head; }

static int cmdq_push(script_item_t it)
{
  uint8_t next = (uint8_t)(q_tail + 1) % CMDQ_CAP;
  if (next == q_head)
    return 0;
  cmdq[q_tail] = it;
  q_tail = next;
  return 1;
}

static int cmdq_pop(script_item_t *out)
{
  if (cmdq_empty())
    return 0;
  *out = cmdq[q_head];
  q_head = (uint8_t)(q_head + 1) % CMDQ_CAP;
  return 1;
}

static inline uint8_t cmdq_count(void)
{
  return (q_tail >= q_head) ? (q_tail - q_head) : (CMDQ_CAP - q_head + q_tail);
}

static inline void cmdq_clear(void)
{
  __disable_irq();
  q_head = q_tail = 0;
  __enable_irq();
}

/* Ack helper */

static volatile uint8_t uart3_tx_busy = 0;
void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart)
{
  if (huart->Instance == USART3)
    uart3_tx_busy = 0;
}

static void send_ack(void)
{
  static const uint8_t msg[] = "OK\n";
  if (uart3_tx_busy)
    return; // or queue it
  uart3_tx_busy = 1;
  (void)HAL_UART_Transmit_IT(&huart3, (uint8_t *)msg, sizeof(msg) - 1);
  cmdq_clear();
}

// to send after each command
static void send_ack_one_cmd(void)
{
  static const uint8_t msg[] = "done\n";
  if (uart3_tx_busy)
    return; // or queue it
  uart3_tx_busy = 1;
  (void)HAL_UART_Transmit_IT(&huart3, (uint8_t *)msg, sizeof(msg) - 1);
}

// ---- Distance control state ----
volatile uint16_t enc_start_a = 0, enc_start_b = 0;
volatile int32_t target_counts = 0; // +ve forward, -ve reverse

#define WHEEL_DIAM_CM 5.7f // was 6.0
#define ENC_PPR 330
#define ENC_MODE_X4 4
#define ENC_CPR (ENC_PPR * ENC_MODE_X4)

#define WHEEL_CIRC_CM (3.14159f * WHEEL_DIAM_CM)
#define COUNTS_PER_CM ((float)ENC_CPR / WHEEL_CIRC_CM)

#define PWM_MAX 7199
#define PWM_RUN 3800 // your current "run" duty // used to be 4500, 4000
#define PWM_MIN 6800
#define PWM_INNER 6000

//luther direction higher value = slower
#define FWD_LEFT_COMPARE_SCALE   1.060f
#define FWD_RIGHT_COMPARE_SCALE  1.000f

/* Starting values only — tune from telemetry. */
#define REV_LEFT_COMPARE_SCALE   0.980f
#define REV_RIGHT_COMPARE_SCALE  1.000f

/* --- Closed-loop yaw turn controller ------------------------------------- luther
 *
 * Motor PWM is inverted by the H-bridge wiring used below:
 *   compare == PWM_MAX -> brake / zero drive
 *   smaller compare    -> more drive
 *
 * For that reason the controller works in positive "effort counts" and only
 * converts effort to a timer compare value at the final output step.
 */
volatile float arc_target_angle = 0.0f;

#define TURN_KP_EFFORT_PER_DEG       32.0f
#define TURN_KI_EFFORT_PER_DEG_S      0.0f  // start at zero; integral increases overshoot
#define TURN_KD_EFFORT_PER_DPS        2.0f
#define TURN_I_LIMIT_DEG_S           60.0f

#define TURN_OUTER_EFFORT_MAX      2060.0f  // approximately the old 4800 * 1.07 command
#define TURN_OUTER_EFFORT_MIN       650.0f
#define TURN_INNER_EFFORT_RATIO_R     0.42f
#define TURN_INNER_EFFORT_RATIO_L     0.42f

#define TURN_FINISH_TOL_DEG           0.5f //tighten the finish tolerance by decreasing
#define TURN_BRAKE_LOOKAHEAD_S        0.007f // main parameter for consistent overshoot, Overshooting: increase look-ahead
#define TURN_SETTLE_MS               150U
#define TURN_RETRY_SERVO_MS           80U
#define TURN_MAX_APPROACHES            3U
#define TURN_TIMEOUT_BASE_MS        1500U
#define TURN_TIMEOUT_PER_DEG_MS        80U

#define GYRO_PERIOD_MS                10U
#define GYRO_RATE_DEADBAND_DPS         0.50f
#define GYRO_STALE_TIMEOUT_MS         100U
#define GYRO_RETRY_DELAY_MS          1000U
#define GYRO_MAX_CONSECUTIVE_FAILURES   3U

#define INTER_CMD_MS 500 // tweak 80–200ms, is the delay for inbetween commands
#define TURN_DELAY 50
#define TURN_DELAY_LEFT 100
#define TURN_DELAY_RIGHT 100
#define SLIDE_CMD_MS 350

// --- Steering mode (no angles; tokens like "fr", "fl") ---
typedef enum
{
  TURN_NONE = 0,
  TURN_LEFT,
  TURN_RIGHT
} turn_t;
volatile turn_t cmd_turn = TURN_NONE;

//    calibrated servo CCRs:
//    htim12.Instance->CCR2 = 230; // extreme right
//    osDelay(3000);
//    htim12.Instance->CCR2 = 180; // half right
//    htim12.Instance->CCR2 = 120; // half left
//    osDelay(3000);
//    htim12.Instance->CCR2 = 100; // extreme left

// luther CCR
#define SERVO_CENTER_CCR 157            // straight (you already use ~152) /155
#define SERVO_CENTER_AFTERLEFT_CCR 164  // latest value supplied by user
#define SERVO_CENTER_AFTERRIGHT_CCR 151 // latest value supplied by user
#define SERVO_RIGHT_CCR 240             // <-- set to your "forward-right" CCR 250
#define SERVO_LEFT_CCR 110              // <-- set to your "forward-left"  CCR 107
#define SERVO_REVERSE_LEFT_CCR 110      // 112
#define SERVO_REVERSE_RIGHT_CCR 240

#define SPEED_LPF_TAU 0.05f // ~0.2 s LPF for encoder speed

/* float is atomic on this STM32 and has ample precision for robot yaw. */
volatile float total_angle = 0.0f;  // updated in gyroTask
volatile float target_angle = 0.0f; // locked when a straight move starts
volatile float error_angle = 0.0f;  // computed in motorTask
volatile float TURN_DEG = 90.0f;

// Gyro and turn-controller state exposed to the telemetry task.
volatile float gyro_bias_dps = 0.0f;
volatile float gyro_yaw_rate_dps = 0.0f;
volatile uint8_t gyro_healthy = 0U;
volatile uint32_t gyro_last_good_tick = 0U;
//static uint8_t bias_locked = 0;

//luther turn start
typedef enum
{
  TURN_CTRL_IDLE = 0,
  TURN_CTRL_DRIVE,
  TURN_CTRL_SETTLE
} turn_control_phase_t;

volatile turn_control_phase_t turn_control_phase = TURN_CTRL_IDLE;
volatile float turn_error_deg = 0.0f;
volatile float turn_effort_cmd = 0.0f;
volatile int turn_left_pwm = PWM_MAX;
volatile int turn_right_pwm = PWM_MAX;

/* Straight-controller outputs exposed to EncoderTask telemetry. */
volatile int straight_left_pwm = PWM_MAX;
volatile int straight_right_pwm = PWM_MAX;
volatile int straight_servo_ccr = SERVO_CENTER_CCR;

static float turn_i_error_deg_s = 0.0f;
static uint32_t turn_pid_last_tick = 0U;
static uint32_t turn_settle_until_tick = 0U;
static uint32_t turn_timeout_tick = 0U;
static uint8_t turn_approach_count = 0U;
// luther turn end

volatile uint32_t turn_motor_enable_tick = 0; // when motors are allowed to start for turns

#define OBSTACLE_STOP_CM 26
#define OBSTACLE_REV_CM 20 // 25

#define US_BACK_CLEAR_CM 20 // 25

volatile uint8_t arc_postforward_cm = 0;

// Gyro scale calibration. 0.989 means a raw 91-degree reading is treated as 90.
volatile float GYRO_SCALE_TRIM = 0.989f;

// ir
// ADC1 DMA buffer (PC0->ADC1_IN10, PC1->ADC1_IN11)
volatile uint16_t ir_adc[2] = {0, 0};

// Values produced by IR_Task, consumed by OLED_Task
volatile uint16_t ir0_raw = 0, ir1_raw = 0;
volatile float ir0_v = 0.0f, ir1_v = 0.0f;
volatile uint8_t ir0_obs = 0, ir1_obs = 0; // obstacle flags

// threshold voltage
#define IR_VOLT_OBS 0.80f // should be 30 cm for GP2Y0A21 (tune in test)

// floating problem
volatile uint16_t ir0_mV = 0, ir1_mV = 0; // 0..3300
#define IR_MV_OBS 800                     // 1.10 V -> 1100

// obstacle mode
#define OBST_MODE_NONE 0
#define OBST_MODE_US 1         // ultrasound
#define OBST_MODE_IR_RIGHT 2   // stop when right IR says "no obstacle" (0)
#define OBST_MODE_IR_LEFT 3    // stop for left IR
#define OBST_MODE_US_BACK 4    // reverse forever until us
#define OBST_MODE_IR_RIGHT_O 5 // stop when right IR says "obstacle" (1)
#define OBST_MODE_IR_LEFT_O 6
#define OBST_MODE_US_T 7 // for FU

volatile uint8_t obstacle_stop_mode = OBST_MODE_NONE;

volatile uint16_t us_stop_cm = 26;     // set by FUxx each time, default 26
volatile uint8_t us_allow_reverse = 1; // 1=FU (reverse on overshoot), 0=FX (just stop)
/* --- Odometry --- */
volatile int32_t odom_counts_run = 0; // counts accumulated in the current move
// volatile int32_t odom_counts_total= 0;   // lifetime counts,
volatile float odom_cm_run = 0.0f; // cached last segment distance (cm)

volatile int32_t odom_counts_run_ir = 0;
volatile float odom_cm_run_ir = 0.0f;

volatile uint8_t seg_rebase = 0; // 1 = rebase last_a/last_b/last_t on next motor tick

// --- Slide control ---
typedef enum
{
  SLIDE_NONE = 0,
  SLIDE_RIGHT = 1,
  SLIDE_LEFT = 2
} slide_t;
typedef enum
{
  SP_NONE = 0,
  SP_TURN_OUT,
  SP_TURN_IN,
  SP_RECENTER
} slide_phase_t;

volatile slide_t slide_mode = SLIDE_NONE;     // active slide direction
volatile slide_phase_t slide_phase = SP_NONE; // OUT -> IN
volatile double slide_origin_heading = 0.0;   // heading at slide start
volatile double slide_return_heading = 0.0;
// volatile double        slide_out_target     = 0.0; // origin ± 45°

#define SLIDE_ANGLE_DEG 50.0
#define SERVO_SLIDERIGHT_CCR 245
#define SERVO_SLIDELEFT_CCR 100

// --- Slide PWM tunables
#define SLIDE_OUTER_PWM 5000 // outer-wheel duty
#define SLIDE_INNER_PWM 6500 // inner-wheel duty

// attempt for US
static volatile uint8_t us_waiting_fall = 0; // 0: wait rising, 1: wait falling
static volatile uint16_t us_echo_ticks = 0;  // width in µs (with PSC=15 => 1MHz)

// OLED pages
volatile uint8_t display_page = 0;
#define TOTAL_PAGES 2   // Page 0 and Page 1

// IR sensor distance
volatile float ir0_distance_cm = 0.0f;
volatile float ir1_distance_cm = 0.0f;

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_DMA_Init(void);
static void MX_TIM4_Init(void);
static void MX_TIM2_Init(void);
static void MX_TIM3_Init(void);
static void MX_USART3_UART_Init(void);
static void MX_TIM9_Init(void);
static void MX_TIM12_Init(void);
static void MX_I2C2_Init(void);
static void MX_TIM8_Init(void);
static void MX_ADC1_Init(void);
static void MX_USART2_UART_Init(void);
void ledTask(void const * argument);
void oledTask(void const * argument);
void motorTask(void const * argument);
void encoderTask(void const * argument);
void gyroTask(void const * argument);
void ultrasoundTask(void const * argument);
void irTask(void const * argument);

/* USER CODE BEGIN PFP */

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */
// ultrasonic
float speedOfSound = 0.0343 / 2;

// delay for US
static inline void delay_us(uint32_t us)
{
  uint32_t start = DWT->CYCCNT;
  uint32_t ticks = us * (SystemCoreClock / 1000000U);
  while ((DWT->CYCCNT - start) < ticks)
  {
    __NOP();
  }
}

void DWT_Delay_Init(void)
{
  CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
  DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

static inline void motor_forward(void)
{
  // MOTORA on TIM4: CH3 = IN2, CH4 = IN1
  __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_3, PWM_RUN);
  __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_4, PWM_MAX);

  // MOTORB on TIM9: CH1 = IN2, CH2 = IN1
  __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_1, PWM_RUN);
  __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_2, PWM_MAX);
}

static inline void motor_reverse(void)
{
  __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_3, PWM_MAX);
  __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_4, PWM_RUN);

  __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_1, PWM_MAX);
  __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_2, PWM_RUN);
}

static inline void motor_brake(void) // both high -> fast brake (your previous "stop")
{
  __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_3, PWM_MAX);
  __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_4, PWM_MAX);

  __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_1, PWM_MAX);
  __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_2, PWM_MAX);
}

static inline void left_forward_duty(int duty)
{
  __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_3, duty);    // IN2 (PWM)
  __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_4, PWM_MAX); // IN1 high -> FWD
}
static inline void right_forward_duty(int duty)
{
  __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_1, duty);    // IN2 (PWM)
  __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_2, PWM_MAX); // IN1 high -> FWD
}
static inline void left_coast(void)
{
  __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_3, 0);
  __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_4, 0);
}
static inline void right_coast(void)
{
  __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_1, 0);
  __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_2, 0);
}

static inline void left_reverse_duty(int duty)
{
  // reverse on left: IN1 = PWM (CH4), IN2 = HIGH (CH3)
  __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_3, PWM_MAX); // IN2 high
  __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_4, duty);    // IN1 pwm
}
static inline void right_reverse_duty(int duty)
{
  // reverse on right: IN1 = PWM (CH2), IN2 = HIGH (CH1)
  __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_1, PWM_MAX); // IN2 high
  __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_2, duty);    // IN1 pwm
}

// luther turn start
static uint16_t current_center_ccr = SERVO_CENTER_CCR;
static inline void set_servo_center(void) { htim12.Instance->CCR2 = current_center_ccr; }
static inline void set_servo_right(void) { htim12.Instance->CCR2 = SERVO_RIGHT_CCR; }
static inline void set_servo_reverse_right(void) { htim12.Instance->CCR2 = SERVO_REVERSE_RIGHT_CCR; }
static inline void set_servo_left(void) { htim12.Instance->CCR2 = SERVO_LEFT_CCR; }
static inline void set_servo_reverse_left(void) { htim12.Instance->CCR2 = SERVO_REVERSE_LEFT_CCR; }
static inline void set_servo_center_afterleft(void)
{
    current_center_ccr = SERVO_CENTER_AFTERLEFT_CCR;
    htim12.Instance->CCR2 = current_center_ccr;
}

static inline void set_servo_center_afterright(void)
{
    current_center_ccr = SERVO_CENTER_AFTERRIGHT_CCR;
    htim12.Instance->CCR2 = current_center_ccr;
}

static inline int clamp_pwm_compare(int value)
{
  if (value < 0)
    return 0;
  if (value > PWM_MAX)
    return PWM_MAX;
  return value;
}

static inline bool is_turn_command(int command)
{
  return command == CMD_ARC_RIGHT ||
         command == CMD_ARC_LEFT ||
         command == CMD_ARC_RIGHT_REV ||
         command == CMD_ARC_LEFT_REV;
}

static inline bool is_reverse_turn_command(int command)
{
  return command == CMD_ARC_RIGHT_REV || command == CMD_ARC_LEFT_REV;
}

static inline bool is_right_steer_turn(int command)
{
  return command == CMD_ARC_RIGHT || command == CMD_ARC_RIGHT_REV;
}

/*
 * Sign of yaw motion produced by each command:
 *   FR and RL reduce total_angle; FL and RR increase it.
 */
static inline float turn_yaw_direction(int command)
{
  return (command == CMD_ARC_LEFT || command == CMD_ARC_RIGHT_REV) ? 1.0f : -1.0f;
}

static void set_turn_servo_for_command(int command)
{
  if (command == CMD_ARC_RIGHT)
    set_servo_right();
  else if (command == CMD_ARC_LEFT)
    set_servo_left();
  else if (command == CMD_ARC_RIGHT_REV)
    set_servo_reverse_right();
  else if (command == CMD_ARC_LEFT_REV)
    set_servo_reverse_left();
}

static void center_servo_after_turn(int command)
{
  if (is_right_steer_turn(command))
    set_servo_center_afterright();
  else
    set_servo_center_afterleft();
}

static void reset_turn_controller(void)
{
  turn_i_error_deg_s = 0.0f;
  turn_pid_last_tick = HAL_GetTick();
  turn_settle_until_tick = 0U;
  turn_timeout_tick = turn_pid_last_tick + TURN_TIMEOUT_BASE_MS +
                      (uint32_t)(TURN_DEG * (float)TURN_TIMEOUT_PER_DEG_MS);
  turn_approach_count = 1U;

  turn_error_deg = arc_target_angle - total_angle;
  turn_effort_cmd = 0.0f;
  turn_left_pwm = PWM_MAX;
  turn_right_pwm = PWM_MAX;
  turn_control_phase = TURN_CTRL_DRIVE;
}

static void stop_turn_controller(void)
{
  turn_i_error_deg_s = 0.0f;
  turn_pid_last_tick = 0U;
  turn_settle_until_tick = 0U;
  turn_timeout_tick = 0U;
  turn_approach_count = 0U;

  turn_effort_cmd = 0.0f;
  turn_left_pwm = PWM_MAX;
  turn_right_pwm = PWM_MAX;
  turn_control_phase = TURN_CTRL_IDLE;
}

static int pwm_compare_from_effort(float effort)
{
  int compare = PWM_MAX - (int)(effort + 0.5f);
  return clamp_pwm_compare(compare);
}

static void drive_turn_wheels(int command, int outer_pwm, int inner_pwm)
{
  int left_pwm;
  int right_pwm;

  /* With right steering the left wheel is outer; with left steering it is right. */
  if (is_right_steer_turn(command))
  {
    left_pwm = outer_pwm;
    right_pwm = inner_pwm;
  }
  else
  {
    left_pwm = inner_pwm;
    right_pwm = outer_pwm;
  }

  left_pwm = clamp_pwm_compare(left_pwm);
  right_pwm = clamp_pwm_compare(right_pwm);

  turn_left_pwm = left_pwm;
  turn_right_pwm = right_pwm;

  if (is_reverse_turn_command(command))
  {
    left_reverse_duty(left_pwm);
    right_reverse_duty(right_pwm);
  }
  else
  {
    /* Always command BOTH wheels. The old FR branch omitted the left wheel. */
    left_forward_duty(left_pwm);
    right_forward_duty(right_pwm);
  }
}

static void finish_turn_command(int completed_command)
{
  motor_brake();
  center_servo_after_turn(completed_command);
  stop_turn_controller();

  /* A following straight segment should hold the heading actually reached. */
  target_angle = total_angle;

  if (arc_postforward_cm > 0U)
  {
    enc_start_a = (uint16_t)__HAL_TIM_GET_COUNTER(&htim2);
    enc_start_b = (uint16_t)__HAL_TIM_GET_COUNTER(&htim3);

    int32_t counts = (int32_t)(arc_postforward_cm * COUNTS_PER_CM + 0.5f);
    obstacle_stop_mode = OBST_MODE_NONE;
    seg_rebase = 1U;

    if (is_reverse_turn_command(completed_command))
    {
      target_counts = -counts;
      uart_cmd = CMD_REVERSE;
    }
    else
    {
      target_counts = counts;
      uart_cmd = CMD_FORWARD;
    }

    arc_postforward_cm = 0U;
  }
  else
  {
    uart_cmd = CMD_NONE;
    next_start_tick = HAL_GetTick() + INTER_CMD_MS;
  }
} //luther turn helper end

static const char *uart_cmd_to_string(void)
{
  switch (uart_cmd)
  {
  case CMD_NONE:
    return "NONE";
  case CMD_FORWARD:
    return "FORWARD";
  case CMD_REVERSE:
    return "REVERSE";
  case CMD_STOP:
    return "STOP";
  case CMD_ARC_RIGHT:
    return "ARC_RIGHT";
  case CMD_ARC_LEFT:
    return "ARC_LEFT";
  case CMD_ARC_RIGHT_REV:
    return "ARC_RR";
  case CMD_ARC_LEFT_REV:
    return "ARC_RL";
  default:
    return "?";
  }
}

// to take a whole string of commands and break it up
static void parse_and_enqueue_script(char *line)
{
  // replace commas with spaces so strtok can split both
  for (char *p = line; *p; ++p)
    if (*p == ',')
      *p = ' ';

  char *tok = strtok(line, " \t");
  while (tok)
  {

    if (strcmp(tok, "rst") == 0)
    {
      abort_now = 1; // handled in motorTask ASAP
      // optional: drop the rest of the line
      break;
    }
    script_item_t it = {SCMD_NONE, 0};

    // tokens already lowercased in Rx callback
    if (strcmp(tok, "fir") == 0)
    {
      it.type = SCMD_FIR;
      it.value = 0;
    }
    else if (strcmp(tok, "fil") == 0)
    {
      it.type = SCMD_FIL;
      it.value = 0;
    }
    else if (strcmp(tok, "firo") == 0)
    {
      it.type = SCMD_FIRO;
      it.value = 0;
    }
    else if (strcmp(tok, "filo") == 0)
    {
      it.type = SCMD_FILO;
      it.value = 0;
    }
    else if (strcmp(tok, "sr") == 0)
    {
      it.type = SCMD_SLIDE_R;
      it.value = 0;
    }
    else if (strcmp(tok, "sl") == 0)
    {
      it.type = SCMD_SLIDE_L;
      it.value = 0;
    }
    else if (tok[0] == 'f' && tok[1] == 'x')
    {
      it.type = SCMD_FX;
      it.value = atoi(&tok[2]);
    }
    else if (tok[0] == 'f' && tok[1] == 'u')
    {
      it.type = SCMD_FU;
      it.value = atoi(&tok[2]);
    }
    else if (tok[0] == 'f' && tok[1] == 'r')
    {
      it.type = SCMD_ARC_FR;
      it.value = atoi(&tok[2]);
    }
    else if (tok[0] == 'f' && tok[1] == 'l')
    {
      it.type = SCMD_ARC_FL;
      it.value = atoi(&tok[2]);
    }
    else if (tok[0] == 'r' && tok[1] == 'r')
    {
      it.type = SCMD_ARC_RR;
      it.value = atoi(&tok[2]);
    }
    else if (tok[0] == 'r' && tok[1] == 'l')
    {
      it.type = SCMD_ARC_RL;
      it.value = atoi(&tok[2]);
    }
    else if (tok[0] == 'f')
    {
      it.type = SCMD_FWD_CM;
      it.value = atoi(&tok[1]);
    }
    else if (tok[0] == 'r')
    {
      it.type = SCMD_REV_CM;
      it.value = atoi(&tok[1]);
    }
    else if (tok[0] == 's')
    {
      it.type = SCMD_STOP;
      it.value = 0;
    }

    if (it.type != SCMD_NONE)
    {
      // Since we’re in an ISR callback when called from Rx, guard briefly
      //__disable_irq();
      int ok = cmdq_push(it);
      //__enable_irq();
      if (!ok)
      {
        const char emsg[] = "ERR:QUEUE\r\n";
        //        HAL_UART_Transmit(&huart3,(uint8_t*)emsg,sizeof(emsg)-1,0xFFFF);
        // drop the rest if full
        break;
      }
    }
    tok = strtok(NULL, " \t");
  }
  script_item_t eos = {SCMD_EOS, 0};
  (void)cmdq_push(eos);
}

static const char *telemetry_name_for_cmd(script_cmd_t type)
{
    switch (type)
    {
    case SCMD_FWD_CM:
        return "FWD_CM";

    case SCMD_REV_CM:
        return "REV_CM";

    case SCMD_ARC_FR:
        return "ARC_FR";

    case SCMD_ARC_FL:
        return "ARC_FL";

    case SCMD_ARC_RR:
        return "ARC_RR";

    case SCMD_ARC_RL:
        return "ARC_RL";

    case SCMD_SLIDE_R:
        return "SLIDE_R";

    case SCMD_SLIDE_L:
        return "SLIDE_L";

    case SCMD_STOP:
        return "STOP";

    case SCMD_FIR:
        return "FIR";

    case SCMD_FIL:
        return "FIL";

    case SCMD_FIRO:
        return "FIRO";

    case SCMD_FILO:
        return "FILO";

    case SCMD_FU:
        return "FU";

    case SCMD_FX:
        return "FX";

    default:
        return NULL;
    }
}

// pop from queue and set all the variables needed, then change the uart_cmd
static int start_next_from_queue(void)
{
  script_item_t it;
  if (!cmdq_pop(&it))
    return 0;

  const char *telemetry_name = telemetry_name_for_cmd(it.type);

  if (telemetry_name != NULL)
  {
      Telemetry_StartCommand(telemetry_name, it.value);
  }

  switch (it.type)
  {

  case SCMD_FX: // fall through — same setup, just different reverse flag
  case SCMD_FU:
  {
    // Forward "forever" but stop when ultrasound <= us_stop_cm
    enc_start_a = (uint16_t)__HAL_TIM_GET_COUNTER(&htim2);
    enc_start_b = (uint16_t)__HAL_TIM_GET_COUNTER(&htim3);
    target_angle = total_angle;
    set_servo_center();

    // reset odometry for reporting
    odom_counts_run = 0;
    odom_cm_run = 0.0f;

    target_counts = INT32_MAX;                                           // run "forever"
    us_stop_cm = (it.value > 0) ? (uint16_t)it.value : OBSTACLE_STOP_CM; // per-move threshold
    us_allow_reverse = (it.type == SCMD_FU) ? 1 : 0;                     // FU=reverse, FX=just stop
    obstacle_stop_mode = OBST_MODE_US_T;                                 // our new mode
    uart_cmd = CMD_FORWARD;
    seg_rebase = 1; // clean speed/odom baselines
    return 1;
  }

  case SCMD_FIRO:
  {
    enc_start_a = (uint16_t)__HAL_TIM_GET_COUNTER(&htim2);
    enc_start_b = (uint16_t)__HAL_TIM_GET_COUNTER(&htim3);
    target_angle = total_angle;
    set_servo_center();

    odom_counts_run = 0;
    odom_cm_run = 0.0f;

    target_counts = INT32_MAX; // run “forever”
    obstacle_stop_mode = OBST_MODE_IR_RIGHT_O;
    uart_cmd = CMD_FORWARD;
    seg_rebase = 1; // <--- rebase on entry
    return 1;
  }

  case SCMD_FILO:
  {
    enc_start_a = (uint16_t)__HAL_TIM_GET_COUNTER(&htim2);
    enc_start_b = (uint16_t)__HAL_TIM_GET_COUNTER(&htim3);
    target_angle = total_angle;
    set_servo_center();

    odom_counts_run = 0;
    odom_cm_run = 0.0f;

    target_counts = INT32_MAX;                // run “forever”
    obstacle_stop_mode = OBST_MODE_IR_LEFT_O; // NEW mode
    uart_cmd = CMD_FORWARD;
    seg_rebase = 1; // <--- rebase on entry
    return 1;
  }

  case SCMD_FIR:
  {
    // forward "forever" until right IR reports 0 (no obstacle)
    enc_start_a = (uint16_t)__HAL_TIM_GET_COUNTER(&htim2);
    enc_start_b = (uint16_t)__HAL_TIM_GET_COUNTER(&htim3);
    target_angle = total_angle;
    set_servo_center();

    odom_counts_run_ir = 0;
    odom_cm_run_ir = 0.0f;

    target_counts = INT32_MAX;               // sentinel: distance won't stop us
    obstacle_stop_mode = OBST_MODE_IR_RIGHT; // NEW mode
    uart_cmd = CMD_FORWARD;
    seg_rebase = 1; // <--- rebase on entry
    return 1;
  }
  case SCMD_FIL:
  {
    // forward "forever" until right IR reports 0 (no obstacle)
    enc_start_a = (uint16_t)__HAL_TIM_GET_COUNTER(&htim2);
    enc_start_b = (uint16_t)__HAL_TIM_GET_COUNTER(&htim3);
    target_angle = total_angle;
    set_servo_center();

    odom_counts_run_ir = 0;
    odom_cm_run_ir = 0.0f;

    target_counts = INT32_MAX;              // sentinel: distance won't stop us
    obstacle_stop_mode = OBST_MODE_IR_LEFT; // IR LEFT
    uart_cmd = CMD_FORWARD;
    seg_rebase = 1; // <--- rebase on entry
    return 1;
  }
  case SCMD_FWD_CM:
  {
    int cm = it.value;
    enc_start_a = (uint16_t)__HAL_TIM_GET_COUNTER(&htim2);
    enc_start_b = (uint16_t)__HAL_TIM_GET_COUNTER(&htim3);
    target_angle = total_angle;
    set_servo_center();

    if (cm > 0)
    {
      // normal distance move
      int32_t tgt = (int32_t)(cm * COUNTS_PER_CM + 0.5f);
      target_counts = tgt;
      obstacle_stop_mode = OBST_MODE_NONE; // ensure off
      uart_cmd = CMD_FORWARD;
    }
    else
    {
      // use ultrasound just go forward forever
      obstacle_stop_mode = OBST_MODE_US;
      target_counts = INT32_MAX; // sentinel; we won't use it
      odom_counts_run = 0;       // reset US segment odometer
      odom_cm_run = 0.0f;
      uart_cmd = CMD_FORWARD;
    }
    seg_rebase = 1; // <--- rebase on entry
    return 1;
  }
  case SCMD_REV_CM:
  {
    int cm = (it.value > 0) ? it.value : 50;
    enc_start_a = (uint16_t)__HAL_TIM_GET_COUNTER(&htim2);
    enc_start_b = (uint16_t)__HAL_TIM_GET_COUNTER(&htim3);
    int32_t tgt = -(int32_t)(cm * COUNTS_PER_CM + 0.5f);
    target_counts = tgt;
    target_angle = total_angle;
    set_servo_center();
    uart_cmd = CMD_REVERSE;
    seg_rebase = 1;
    return 1;
  }

  case SCMD_ARC_FR:
    TURN_DEG = (it.value >= 0) ? (float)it.value : -(float)it.value;
    arc_target_angle = total_angle - TURN_DEG;
    set_servo_right();
    turn_motor_enable_tick = HAL_GetTick() + TURN_DELAY_RIGHT;
    arc_postforward_cm = 0;
    uart_cmd = CMD_ARC_RIGHT;
    reset_turn_controller();
    return 1;

  case SCMD_ARC_FL:
    TURN_DEG = (it.value >= 0) ? (float)it.value : -(float)it.value;
    arc_target_angle = total_angle + TURN_DEG;
    set_servo_left();
    turn_motor_enable_tick = HAL_GetTick() + TURN_DELAY_LEFT; // <-- add
    arc_postforward_cm = 0;
    uart_cmd = CMD_ARC_LEFT;
    reset_turn_controller();
    return 1;

  case SCMD_ARC_RR:
    TURN_DEG = (it.value >= 0) ? (float)it.value : -(float)it.value;
    arc_target_angle = total_angle + TURN_DEG;
    set_servo_reverse_right();
    turn_motor_enable_tick = HAL_GetTick() + TURN_DELAY; // <-- add
    arc_postforward_cm = 1;
    uart_cmd = CMD_ARC_RIGHT_REV;
    reset_turn_controller();
    return 1;

  case SCMD_ARC_RL:
    TURN_DEG = (it.value >= 0) ? (float)it.value : -(float)it.value;
    arc_target_angle = total_angle - TURN_DEG;
    set_servo_reverse_left();
    turn_motor_enable_tick = HAL_GetTick() + TURN_DELAY; // <-- add
    arc_postforward_cm = 0;
    uart_cmd = CMD_ARC_LEFT_REV;
    reset_turn_controller();
    return 1;

  case SCMD_STOP:
    motor_brake();
    stop_turn_controller();
    set_servo_center();
    uart_cmd = CMD_STOP;
    return 1;

  case SCMD_EOS:
    send_ack(); // <--- ACK the just-finished line
                // Do NOT set uart_cmd; just return. The idle loop will pick up the next item
    return 1;

  case SCMD_SLIDE_R:
  {

    // arm the slide state machine (RIGHT: heading goes -45)
    slide_origin_heading = arc_target_angle; // save the current heading for slide back
    //		slide_out_target = arc_target_angle - SLIDE_ANGLE_DEG;
    slide_return_heading = arc_target_angle + SLIDE_ANGLE_DEG;
    arc_target_angle = arc_target_angle - SLIDE_ANGLE_DEG;
    //		arc_target_angle = arc_target_angle;
    slide_mode = SLIDE_RIGHT;
    slide_phase = SP_TURN_OUT;
    // ensure we are in forward mode; if idle or not forward, start forward-forever
    if (uart_cmd != CMD_FORWARD)
    {
      enc_start_a = (uint16_t)__HAL_TIM_GET_COUNTER(&htim2);
      enc_start_b = (uint16_t)__HAL_TIM_GET_COUNTER(&htim3);
      //            target_angle     = total_angle;
      //            arc_target_angle = total_angle;           // lock straight reference
      set_servo_center();

      target_counts = INT32_MAX; // forward "forever"
      obstacle_stop_mode = OBST_MODE_NONE;
      uart_cmd = CMD_FORWARD;
    }

    return 1;
  }

  case SCMD_SLIDE_L:
  {

    // arm the slide state machine (LEFT: heading goes +45)
    slide_origin_heading = arc_target_angle;
    //    		slide_out_target = arc_target_angle + SLIDE_ANGLE_DEG;
    slide_return_heading = arc_target_angle - SLIDE_ANGLE_DEG;
    arc_target_angle = arc_target_angle + SLIDE_ANGLE_DEG;
    //		arc_target_angle = arc_target_angle;
    slide_mode = SLIDE_LEFT;
    slide_phase = SP_TURN_OUT;
    // ensure we are in forward mode; if idle or not forward, start forward-forever
    if (uart_cmd != CMD_FORWARD)
    {
      enc_start_a = (uint16_t)__HAL_TIM_GET_COUNTER(&htim2);
      enc_start_b = (uint16_t)__HAL_TIM_GET_COUNTER(&htim3);
      //                target_angle     = total_angle;
      //                arc_target_angle = total_angle;           // lock straight reference
      set_servo_center();

      target_counts = INT32_MAX; // forward "forever"
      obstacle_stop_mode = OBST_MODE_NONE;
      uart_cmd = CMD_FORWARD;
    }

    return 1;
  }

  default:
    break;
  }
  return 0;
}

// ultrasound

// IR conversion calculation
float Voltage_To_Distance_CM(float v) {
    if (v < 0.1f) return 80.0f; // Guard against near-zero division or noise
    float cm = 27.86f * powf(v, -1.15f);
    if (cm > 80.0f) return 80.0f;
    if (cm < 10.0f) return 10.0f;
    return cm;
}

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  const uint32_t reset_cause_flags = RCC->CSR;

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */
  DWT_Delay_Init();
  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_DMA_Init();
  MX_TIM4_Init();
  MX_TIM2_Init();
  MX_TIM3_Init();
  MX_USART3_UART_Init();
  MX_TIM9_Init();
  MX_TIM12_Init();
  MX_I2C2_Init();
  MX_TIM8_Init();
  MX_ADC1_Init();
  MX_USART2_UART_Init();
  /* USER CODE BEGIN 2 */
  OLED_Init();

  Telemetry_Init(&huart2);

  if (reset_cause_flags & RCC_CSR_IWDGRSTF)
    Telemetry_RecordFault("BOOT_IWDG");
  else if (reset_cause_flags & RCC_CSR_WWDGRSTF)
    Telemetry_RecordFault("BOOT_WWDG");
  else if (reset_cause_flags & RCC_CSR_SFTRSTF)
    Telemetry_RecordFault("BOOT_SOFTWARE");
  else if (reset_cause_flags & RCC_CSR_BORRSTF)
    Telemetry_RecordFault("BOOT_BROWNOUT");
  else if (reset_cause_flags & RCC_CSR_PINRSTF)
    Telemetry_RecordFault("BOOT_PIN");
  else if (reset_cause_flags & RCC_CSR_PORRSTF)
    Telemetry_RecordFault("BOOT_POWER");
  else
    Telemetry_RecordFault("BOOT_OTHER");

  __HAL_RCC_CLEAR_RESET_FLAGS();

  /* Start byte-by-byte UART RX */
  HAL_UART_Receive_IT(&huart3, (uint8_t *)&rx_byte, 1);

  // IR DMA
  HAL_ADC_Start_DMA(&hadc1, (uint32_t *)ir_adc, 2);
  /* USER CODE END 2 */

  /* USER CODE BEGIN RTOS_MUTEX */
  /* add mutexes, ... */
  /* USER CODE END RTOS_MUTEX */

  /* USER CODE BEGIN RTOS_SEMAPHORES */
  /* add semaphores, ... */
  /* USER CODE END RTOS_SEMAPHORES */

  /* USER CODE BEGIN RTOS_TIMERS */
  /* start timers, add new ones, ... */
  /* USER CODE END RTOS_TIMERS */

  /* USER CODE BEGIN RTOS_QUEUES */
  /* add queues, ... */
  /* USER CODE END RTOS_QUEUES */

  /* Create the thread(s) */
  /* definition and creation of LED_Task */
  osThreadDef(LED_Task, ledTask, osPriorityNormal, 0, 128);
  LED_TaskHandle = osThreadCreate(osThread(LED_Task), NULL);

  /* definition and creation of OLED_Task */
  osThreadDef(OLED_Task, oledTask, osPriorityBelowNormal, 0, 384);
  OLED_TaskHandle = osThreadCreate(osThread(OLED_Task), NULL);

  /* definition and creation of Motor_Task */
  osThreadDef(Motor_Task, motorTask, osPriorityAboveNormal, 0, 1024);
  Motor_TaskHandle = osThreadCreate(osThread(Motor_Task), NULL);

  /* definition and creation of Encoder_Task */
  osThreadDef(Encoder_Task, encoderTask, osPriorityBelowNormal, 0, 512);
  Encoder_TaskHandle = osThreadCreate(osThread(Encoder_Task), NULL);

  /* definition and creation of Gyro_Task */
  osThreadDef(Gyro_Task, gyroTask, osPriorityNormal, 0, 384);
  Gyro_TaskHandle = osThreadCreate(osThread(Gyro_Task), NULL);

  /* definition and creation of Ultrasound_Task */
  osThreadDef(Ultrasound_Task, ultrasoundTask, osPriorityBelowNormal, 0, 256);
  Ultrasound_TaskHandle = osThreadCreate(osThread(Ultrasound_Task), NULL);

  /* definition and creation of IR_Task */
  osThreadDef(IR_Task, irTask, osPriorityIdle, 0, 128);
  IR_TaskHandle = osThreadCreate(osThread(IR_Task), NULL);

  /* USER CODE BEGIN RTOS_THREADS */
  /* add threads, ... */
  /* USER CODE END RTOS_THREADS */

  /* Start scheduler */
  osKernelStart();

  /* We should never get here as control is now taken by the scheduler */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {

    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  __HAL_RCC_PWR_CLK_ENABLE();
  __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_NONE;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_HSI;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_0) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief ADC1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_ADC1_Init(void)
{

  /* USER CODE BEGIN ADC1_Init 0 */

  /* USER CODE END ADC1_Init 0 */

  ADC_ChannelConfTypeDef sConfig = {0};

  /* USER CODE BEGIN ADC1_Init 1 */

  /* USER CODE END ADC1_Init 1 */

  /** Configure the global features of the ADC (Clock, Resolution, Data Alignment and number of conversion)
  */
  hadc1.Instance = ADC1;
  hadc1.Init.ClockPrescaler = ADC_CLOCK_SYNC_PCLK_DIV8;
  hadc1.Init.Resolution = ADC_RESOLUTION_12B;
  hadc1.Init.ScanConvMode = ENABLE;
  hadc1.Init.ContinuousConvMode = ENABLE;
  hadc1.Init.DiscontinuousConvMode = DISABLE;
  hadc1.Init.ExternalTrigConvEdge = ADC_EXTERNALTRIGCONVEDGE_NONE;
  hadc1.Init.ExternalTrigConv = ADC_SOFTWARE_START;
  hadc1.Init.DataAlign = ADC_DATAALIGN_RIGHT;
  hadc1.Init.NbrOfConversion = 2;
  hadc1.Init.DMAContinuousRequests = ENABLE;
  hadc1.Init.EOCSelection = ADC_EOC_SEQ_CONV;
  if (HAL_ADC_Init(&hadc1) != HAL_OK)
  {
    Error_Handler();
  }

  /** Configure for the selected ADC regular channel its corresponding rank in the sequencer and its sample time.
  */
  sConfig.Channel = ADC_CHANNEL_10;
  sConfig.Rank = 1;
  sConfig.SamplingTime = ADC_SAMPLETIME_480CYCLES;
  if (HAL_ADC_ConfigChannel(&hadc1, &sConfig) != HAL_OK)
  {
    Error_Handler();
  }

  /** Configure for the selected ADC regular channel its corresponding rank in the sequencer and its sample time.
  */
  sConfig.Channel = ADC_CHANNEL_11;
  sConfig.Rank = 2;
  if (HAL_ADC_ConfigChannel(&hadc1, &sConfig) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN ADC1_Init 2 */

  /* USER CODE END ADC1_Init 2 */

}

/**
  * @brief I2C2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_I2C2_Init(void)
{

  /* USER CODE BEGIN I2C2_Init 0 */

  /* USER CODE END I2C2_Init 0 */

  /* USER CODE BEGIN I2C2_Init 1 */

  /* USER CODE END I2C2_Init 1 */
  hi2c2.Instance = I2C2;
  hi2c2.Init.ClockSpeed = 100000;
  hi2c2.Init.DutyCycle = I2C_DUTYCYCLE_2;
  hi2c2.Init.OwnAddress1 = 0;
  hi2c2.Init.AddressingMode = I2C_ADDRESSINGMODE_7BIT;
  hi2c2.Init.DualAddressMode = I2C_DUALADDRESS_DISABLE;
  hi2c2.Init.OwnAddress2 = 0;
  hi2c2.Init.GeneralCallMode = I2C_GENERALCALL_DISABLE;
  hi2c2.Init.NoStretchMode = I2C_NOSTRETCH_DISABLE;
  if (HAL_I2C_Init(&hi2c2) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN I2C2_Init 2 */

  /* USER CODE END I2C2_Init 2 */

}

/**
  * @brief TIM2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM2_Init(void)
{

  /* USER CODE BEGIN TIM2_Init 0 */

  /* USER CODE END TIM2_Init 0 */

  TIM_Encoder_InitTypeDef sConfig = {0};
  TIM_MasterConfigTypeDef sMasterConfig = {0};

  /* USER CODE BEGIN TIM2_Init 1 */

  /* USER CODE END TIM2_Init 1 */
  htim2.Instance = TIM2;
  htim2.Init.Prescaler = 0;
  htim2.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim2.Init.Period = 65535;
  htim2.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim2.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  sConfig.EncoderMode = TIM_ENCODERMODE_TI12;
  sConfig.IC1Polarity = TIM_ICPOLARITY_RISING;
  sConfig.IC1Selection = TIM_ICSELECTION_DIRECTTI;
  sConfig.IC1Prescaler = TIM_ICPSC_DIV1;
  sConfig.IC1Filter = 10;
  sConfig.IC2Polarity = TIM_ICPOLARITY_RISING;
  sConfig.IC2Selection = TIM_ICSELECTION_DIRECTTI;
  sConfig.IC2Prescaler = TIM_ICPSC_DIV1;
  sConfig.IC2Filter = 10;
  if (HAL_TIM_Encoder_Init(&htim2, &sConfig) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim2, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM2_Init 2 */

  /* USER CODE END TIM2_Init 2 */

}

/**
  * @brief TIM3 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM3_Init(void)
{

  /* USER CODE BEGIN TIM3_Init 0 */

  /* USER CODE END TIM3_Init 0 */

  TIM_Encoder_InitTypeDef sConfig = {0};
  TIM_MasterConfigTypeDef sMasterConfig = {0};

  /* USER CODE BEGIN TIM3_Init 1 */

  /* USER CODE END TIM3_Init 1 */
  htim3.Instance = TIM3;
  htim3.Init.Prescaler = 0;
  htim3.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim3.Init.Period = 65535;
  htim3.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim3.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  sConfig.EncoderMode = TIM_ENCODERMODE_TI12;
  sConfig.IC1Polarity = TIM_ICPOLARITY_RISING;
  sConfig.IC1Selection = TIM_ICSELECTION_DIRECTTI;
  sConfig.IC1Prescaler = TIM_ICPSC_DIV1;
  sConfig.IC1Filter = 10;
  sConfig.IC2Polarity = TIM_ICPOLARITY_RISING;
  sConfig.IC2Selection = TIM_ICSELECTION_DIRECTTI;
  sConfig.IC2Prescaler = TIM_ICPSC_DIV1;
  sConfig.IC2Filter = 10;
  if (HAL_TIM_Encoder_Init(&htim3, &sConfig) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim3, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM3_Init 2 */

  /* USER CODE END TIM3_Init 2 */

}

/**
  * @brief TIM4 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM4_Init(void)
{

  /* USER CODE BEGIN TIM4_Init 0 */

  /* USER CODE END TIM4_Init 0 */

  TIM_ClockConfigTypeDef sClockSourceConfig = {0};
  TIM_MasterConfigTypeDef sMasterConfig = {0};
  TIM_OC_InitTypeDef sConfigOC = {0};

  /* USER CODE BEGIN TIM4_Init 1 */

  /* USER CODE END TIM4_Init 1 */
  htim4.Instance = TIM4;
  htim4.Init.Prescaler = 0;
  htim4.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim4.Init.Period = 7199;
  htim4.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim4.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_Base_Init(&htim4) != HAL_OK)
  {
    Error_Handler();
  }
  sClockSourceConfig.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
  if (HAL_TIM_ConfigClockSource(&htim4, &sClockSourceConfig) != HAL_OK)
  {
    Error_Handler();
  }
  if (HAL_TIM_PWM_Init(&htim4) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim4, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  sConfigOC.OCMode = TIM_OCMODE_PWM1;
  sConfigOC.Pulse = 0;
  sConfigOC.OCPolarity = TIM_OCPOLARITY_HIGH;
  sConfigOC.OCFastMode = TIM_OCFAST_DISABLE;
  if (HAL_TIM_PWM_ConfigChannel(&htim4, &sConfigOC, TIM_CHANNEL_3) != HAL_OK)
  {
    Error_Handler();
  }
  if (HAL_TIM_PWM_ConfigChannel(&htim4, &sConfigOC, TIM_CHANNEL_4) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM4_Init 2 */

  /* USER CODE END TIM4_Init 2 */
  HAL_TIM_MspPostInit(&htim4);

}

/**
  * @brief TIM8 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM8_Init(void)
{

  /* USER CODE BEGIN TIM8_Init 0 */

  /* USER CODE END TIM8_Init 0 */

  TIM_ClockConfigTypeDef sClockSourceConfig = {0};
  TIM_MasterConfigTypeDef sMasterConfig = {0};
  TIM_IC_InitTypeDef sConfigIC = {0};

  /* USER CODE BEGIN TIM8_Init 1 */

  /* USER CODE END TIM8_Init 1 */
  htim8.Instance = TIM8;
  htim8.Init.Prescaler = 16-1;
  htim8.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim8.Init.Period = 65535;
  htim8.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim8.Init.RepetitionCounter = 0;
  htim8.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_Base_Init(&htim8) != HAL_OK)
  {
    Error_Handler();
  }
  sClockSourceConfig.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
  if (HAL_TIM_ConfigClockSource(&htim8, &sClockSourceConfig) != HAL_OK)
  {
    Error_Handler();
  }
  if (HAL_TIM_IC_Init(&htim8) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim8, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  sConfigIC.ICPolarity = TIM_INPUTCHANNELPOLARITY_BOTHEDGE;
  sConfigIC.ICSelection = TIM_ICSELECTION_DIRECTTI;
  sConfigIC.ICPrescaler = TIM_ICPSC_DIV1;
  sConfigIC.ICFilter = 0;
  if (HAL_TIM_IC_ConfigChannel(&htim8, &sConfigIC, TIM_CHANNEL_2) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM8_Init 2 */

  /* USER CODE END TIM8_Init 2 */

}

/**
  * @brief TIM9 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM9_Init(void)
{

  /* USER CODE BEGIN TIM9_Init 0 */

  /* USER CODE END TIM9_Init 0 */

  TIM_ClockConfigTypeDef sClockSourceConfig = {0};
  TIM_OC_InitTypeDef sConfigOC = {0};

  /* USER CODE BEGIN TIM9_Init 1 */

  /* USER CODE END TIM9_Init 1 */
  htim9.Instance = TIM9;
  htim9.Init.Prescaler = 0;
  htim9.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim9.Init.Period = 7199;
  htim9.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim9.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_Base_Init(&htim9) != HAL_OK)
  {
    Error_Handler();
  }
  sClockSourceConfig.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
  if (HAL_TIM_ConfigClockSource(&htim9, &sClockSourceConfig) != HAL_OK)
  {
    Error_Handler();
  }
  if (HAL_TIM_PWM_Init(&htim9) != HAL_OK)
  {
    Error_Handler();
  }
  sConfigOC.OCMode = TIM_OCMODE_PWM1;
  sConfigOC.Pulse = 0;
  sConfigOC.OCPolarity = TIM_OCPOLARITY_HIGH;
  sConfigOC.OCFastMode = TIM_OCFAST_DISABLE;
  if (HAL_TIM_PWM_ConfigChannel(&htim9, &sConfigOC, TIM_CHANNEL_1) != HAL_OK)
  {
    Error_Handler();
  }
  if (HAL_TIM_PWM_ConfigChannel(&htim9, &sConfigOC, TIM_CHANNEL_2) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM9_Init 2 */

  /* USER CODE END TIM9_Init 2 */
  HAL_TIM_MspPostInit(&htim9);

}

/**
  * @brief TIM12 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM12_Init(void)
{

  /* USER CODE BEGIN TIM12_Init 0 */

  /* USER CODE END TIM12_Init 0 */

  TIM_ClockConfigTypeDef sClockSourceConfig = {0};
  TIM_OC_InitTypeDef sConfigOC = {0};

  /* USER CODE BEGIN TIM12_Init 1 */

  /* USER CODE END TIM12_Init 1 */
  htim12.Instance = TIM12;
  htim12.Init.Prescaler = 160;
  htim12.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim12.Init.Period = 1000;
  htim12.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim12.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_Base_Init(&htim12) != HAL_OK)
  {
    Error_Handler();
  }
  sClockSourceConfig.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
  if (HAL_TIM_ConfigClockSource(&htim12, &sClockSourceConfig) != HAL_OK)
  {
    Error_Handler();
  }
  if (HAL_TIM_PWM_Init(&htim12) != HAL_OK)
  {
    Error_Handler();
  }
  sConfigOC.OCMode = TIM_OCMODE_PWM1;
  sConfigOC.Pulse = 0;
  sConfigOC.OCPolarity = TIM_OCPOLARITY_HIGH;
  sConfigOC.OCFastMode = TIM_OCFAST_DISABLE;
  if (HAL_TIM_PWM_ConfigChannel(&htim12, &sConfigOC, TIM_CHANNEL_2) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM12_Init 2 */

  /* USER CODE END TIM12_Init 2 */
  HAL_TIM_MspPostInit(&htim12);

}

/**
  * @brief USART2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_USART2_UART_Init(void)
{

  /* USER CODE BEGIN USART2_Init 0 */

  /* USER CODE END USART2_Init 0 */

  /* USER CODE BEGIN USART2_Init 1 */

  /* USER CODE END USART2_Init 1 */
  huart2.Instance = USART2;
  huart2.Init.BaudRate = 115200;
  huart2.Init.WordLength = UART_WORDLENGTH_8B;
  huart2.Init.StopBits = UART_STOPBITS_1;
  huart2.Init.Parity = UART_PARITY_NONE;
  huart2.Init.Mode = UART_MODE_TX_RX;
  huart2.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart2.Init.OverSampling = UART_OVERSAMPLING_16;
  if (HAL_UART_Init(&huart2) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN USART2_Init 2 */

  /* USER CODE END USART2_Init 2 */

}

/**
  * @brief USART3 Initialization Function
  * @param None
  * @retval None
  */
static void MX_USART3_UART_Init(void)
{

  /* USER CODE BEGIN USART3_Init 0 */

  /* USER CODE END USART3_Init 0 */

  /* USER CODE BEGIN USART3_Init 1 */

  /* USER CODE END USART3_Init 1 */
  huart3.Instance = USART3;
  huart3.Init.BaudRate = 115200;
  huart3.Init.WordLength = UART_WORDLENGTH_8B;
  huart3.Init.StopBits = UART_STOPBITS_1;
  huart3.Init.Parity = UART_PARITY_NONE;
  huart3.Init.Mode = UART_MODE_TX_RX;
  huart3.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart3.Init.OverSampling = UART_OVERSAMPLING_16;
  if (HAL_UART_Init(&huart3) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN USART3_Init 2 */

  /* USER CODE END USART3_Init 2 */

}

/**
  * Enable DMA controller clock
  */
static void MX_DMA_Init(void)
{

  /* DMA controller clock enable */
  __HAL_RCC_DMA2_CLK_ENABLE();

  /* DMA interrupt init */
  /* DMA2_Stream0_IRQn interrupt configuration */
  HAL_NVIC_SetPriority(DMA2_Stream0_IRQn, 5, 0);
  HAL_NVIC_EnableIRQ(DMA2_Stream0_IRQn);

}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};
  /* USER CODE BEGIN MX_GPIO_Init_1 */

  /* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOE_CLK_ENABLE();
  __HAL_RCC_GPIOC_CLK_ENABLE();
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();
  __HAL_RCC_GPIOD_CLK_ENABLE();

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(LED3_GPIO_Port, LED3_Pin, GPIO_PIN_RESET);

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOD, OLED_DC_Pin|OLED_RES_Pin|OLED_SDA_Pin|OLED_SCL_Pin, GPIO_PIN_RESET);

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(US_Trig_GPIO_Port, US_Trig_Pin, GPIO_PIN_RESET);

  /*Configure GPIO pin : LED3_Pin */
  GPIO_InitStruct.Pin = LED3_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(LED3_GPIO_Port, &GPIO_InitStruct);

  /*Configure GPIO pins : OLED_DC_Pin OLED_RES_Pin OLED_SDA_Pin OLED_SCL_Pin */
  GPIO_InitStruct.Pin = OLED_DC_Pin|OLED_RES_Pin|OLED_SDA_Pin|OLED_SCL_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOD, &GPIO_InitStruct);

  /*Configure GPIO pin : US_Trig_Pin */
  GPIO_InitStruct.Pin = US_Trig_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(US_Trig_GPIO_Port, &GPIO_InitStruct);

  /*Configure GPIO pin : OLED_Button_Pin */
  GPIO_InitStruct.Pin = OLED_Button_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(OLED_Button_GPIO_Port, &GPIO_InitStruct);

  /* USER CODE BEGIN MX_GPIO_Init_2 */

  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */
// callback function, when rxbuffer comes in, go to this function
//  my callback function will parse the command

/* --- IR Sensor Helpers --- */

// Convert ADC raw value (0–4095) to volts (0.0–3.3 V)
/*float ADC_To_Voltage(uint16_t raw) {
    return (3.3f * raw) / 4095.0f;
}

// Very rough mapping from voltage to distance in cm
float Voltage_To_Distance_CM(float v) {
    if (v < 0.4f) return 80.0f;
    else if (v < 0.5f) return 60.0f;
    else if (v < 0.7f) return 40.0f;
    else if (v < 1.1f) return 30.0f;
    else if (v < 1.5f) return 20.0f;
    else if (v < 2.2f) return 15.0f;
    else return 10.0f;
}*/

void HCSR04_Trigger(void)
{
  HAL_GPIO_WritePin(US_Trig_GPIO_Port, US_Trig_Pin, GPIO_PIN_RESET);
  HAL_Delay(2);
  HAL_GPIO_WritePin(US_Trig_GPIO_Port, US_Trig_Pin, GPIO_PIN_SET);
  HAL_Delay(1); // Short delay for 10µs pulse
  HAL_GPIO_WritePin(US_Trig_GPIO_Port, US_Trig_Pin, GPIO_PIN_RESET);
}

static inline void HCSR04_Trigger_10us(void)
{
  HAL_GPIO_WritePin(US_Trig_GPIO_Port, US_Trig_Pin, GPIO_PIN_RESET);
  delay_us(2);
  HAL_GPIO_WritePin(US_Trig_GPIO_Port, US_Trig_Pin, GPIO_PIN_SET);
  delay_us(10);
  HAL_GPIO_WritePin(US_Trig_GPIO_Port, US_Trig_Pin, GPIO_PIN_RESET);
}

static inline uint32_t median3_u32(uint32_t a, uint32_t b, uint32_t c)
{
  uint32_t max = (a > b) ? ((a > c) ? a : c) : ((b > c) ? b : c);
  uint32_t min = (a < b) ? ((a < c) ? a : c) : ((b < c) ? b : c);
  return a + b + c - max - min;
}

void HAL_TIM_IC_CaptureCallback(TIM_HandleTypeDef *htim)
{
  if (htim->Instance != TIM8 || htim->Channel != HAL_TIM_ACTIVE_CHANNEL_2) return;

  if (!us_waiting_fall) {
    // Rising edge: reset counter and switch to falling edge
    __HAL_TIM_SET_COUNTER(htim, 0);
    __HAL_TIM_SET_CAPTUREPOLARITY(htim, TIM_CHANNEL_2, TIM_INPUTCHANNELPOLARITY_FALLING);
    us_waiting_fall = 1;
  } else {
    // Falling edge: capture width and switch back to rising edge
    us_echo_ticks = HAL_TIM_ReadCapturedValue(htim, TIM_CHANNEL_2);
    __HAL_TIM_SET_CAPTUREPOLARITY(htim, TIM_CHANNEL_2, TIM_INPUTCHANNELPOLARITY_RISING);
    us_waiting_fall = 0;

    // Convert ticks to cm and update globals
    uint32_t raw_cm = (uint32_t)(us_echo_ticks * (0.0343f / 2.0f) + 0.5f);
    us_cm_hist[us_cm_hist_idx] = raw_cm;
    us_cm_hist_idx = (us_cm_hist_idx + 1U) % 3U;
    if (us_cm_hist_count < 3U) {
      us_cm_hist_count++;
    }
    uint32_t filtered_cm = raw_cm;
    if (us_cm_hist_count == 3U) {
      filtered_cm = median3_u32(us_cm_hist[0], us_cm_hist[1], us_cm_hist[2]);
    }
    distance = (float)filtered_cm;
    echo_debug = filtered_cm;
    new_measurement_ready = true;
  }
}

/*void HAL_TIM_IC_CaptureCallback(TIM_HandleTypeDef *htim)
{
  if (HAL_GPIO_ReadPin(GPIOC, GPIO_PIN_7) == GPIO_PIN_SET)
  {
    tc1 = HAL_TIM_ReadCapturedValue(htim, TIM_CHANNEL_2);
  }
  else
  {
    tc2 = HAL_TIM_ReadCapturedValue(htim, TIM_CHANNEL_2);
    echo = (tc2 > tc1) ? (tc2 - tc1) : (65536 - tc1 + tc2);
    uint32_t raw_cm = (uint32_t)(echo * (0.0343f / 2.0f) + 0.5f);
    us_cm_hist[us_cm_hist_idx] = raw_cm;
    us_cm_hist_idx = (us_cm_hist_idx + 1U) % 3U;
    if (us_cm_hist_count < 3U)
    {
      us_cm_hist_count++;
    }
    uint32_t filtered_cm = raw_cm;
    if (us_cm_hist_count == 3U)
    {
      filtered_cm = median3_u32(us_cm_hist[0], us_cm_hist[1], us_cm_hist[2]);
    }
    distance = (float)filtered_cm;
    echo_debug = filtered_cm;
    new_measurement_ready = true;
  }
}*/

// void HAL_TIM_IC_CaptureCallback(TIM_HandleTypeDef *htim)
//{
//     if (htim->Instance != TIM8 || htim->Channel != HAL_TIM_ACTIVE_CHANNEL_2) return;
//
//     if (!us_waiting_fall) {
//         // Rising edge: start timing
//         __HAL_TIM_SET_COUNTER(htim, 0);
//         __HAL_TIM_SET_CAPTUREPOLARITY(htim, TIM_CHANNEL_2, TIM_INPUTCHANNELPOLARITY_FALLING);
//         us_waiting_fall = 1;
//     } else {
//         // Falling edge: stop timing
//         us_echo_ticks = __HAL_TIM_GET_COMPARE(htim, TIM_CHANNEL_2);  // microseconds
//         __HAL_TIM_SET_CAPTUREPOLARITY(htim, TIM_CHANNEL_2, TIM_INPUTCHANNELPOLARITY_RISING);
//         us_waiting_fall = 0;
//         new_measurement_ready = true;  // tell the task there’s a fresh width
//     }
// }

// keep this callback short, just update the buffer and add to queue once \n
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
  if (huart->Instance == USART3)
  {
    uint8_t c = rx_byte;

    if (c == '\r' || c == '\n')
    {
      /* Do not call strtok(), atoi(), queue code, or command-start code in
       * interrupt context. Publish one complete line for motorTask instead. */
      if (cmd_idx > 0U && !pending_cmd_ready)
      {
        cmd_buf[cmd_idx] = '\0';
        memcpy(pending_cmd_buf, cmd_buf, (size_t)cmd_idx + 1U);
        pending_cmd_ready = 1U;
      }
      cmd_idx = 0U;
    }
    else
    {
      if (cmd_idx < sizeof(cmd_buf) - 1)
      {
        cmd_buf[cmd_idx++] = (char)c;
      }
      else
      {
        cmd_idx = 0U;
      }
    }

    HAL_UART_Receive_IT(&huart3, (uint8_t *)&rx_byte, 1);
  }
}

void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef *hadc)
{
  if (hadc->Instance == ADC1)
  {
    // raw -> mV (rounded)
    uint16_t mV0 = (uint16_t)((3300u * ir_adc[0] + 2047u) / 4095u);
    uint16_t mV1 = (uint16_t)((3300u * ir_adc[1] + 2047u) / 4095u);

    // EMA in integer domain: y = 0.8*y + 0.2*x  ->  y = (4*y + x) / 5
    ir0_mV = (uint16_t)((4u * ir0_mV + mV0) / 5u);
    ir1_mV = (uint16_t)((4u * ir1_mV + mV1) / 5u);

    ir0_raw = ir_adc[0];
    ir1_raw = ir_adc[1];

    // Use threshold in volts -> convert to mV once:
    // #define IR_MV_OBS 1100
    ir0_obs = (ir0_mV >= IR_MV_OBS);
    ir1_obs = (ir1_mV >= IR_MV_OBS);
  }
}

/* USER CODE END 4 */

/* USER CODE BEGIN Header_ledTask */
/**
 * @brief  Function implementing the LED_Task thread.
 * @param  argument: Not used
 * @retval None
 */
/* USER CODE END Header_ledTask */
void ledTask(void const * argument)
{
  /* USER CODE BEGIN 5 */
  /* Infinite loop */
  uint8_t ch = 'A';
  for (;;)
  {
    // HAL_UART_Transmit(&huart3, (uint8_t*)&ch, 1, 0xFFFF); //every toggle STM will transmit ch out
    //    if (ch < 'Z')
    //        ch++;
    //    else ch = 'A';
    HAL_GPIO_TogglePin(LED3_GPIO_Port, LED3_Pin);
    osDelay(1000);
  }
  /* USER CODE END 5 */
}

/* USER CODE BEGIN Header_oledTask */
/**
 * @brief Function implementing the OLED_Task thread.
 * @param argument: Not used
 * @retval None
 */
/* USER CODE END Header_oledTask */
void oledTask(void const * argument)
{
  /* USER CODE BEGIN oledTask */
  char line[32];
  static uint8_t display_page = 0;
  #define TOTAL_PAGES 2

  static GPIO_PinState last_btn_state = GPIO_PIN_SET;

  for (;;)
  {
    // ---- Check Button State (Polling) ----
    GPIO_PinState current_btn_state = HAL_GPIO_ReadPin(OLED_Button_GPIO_Port, OLED_Button_Pin);
    if (last_btn_state == GPIO_PIN_SET && current_btn_state == GPIO_PIN_RESET)
    {
      display_page = (display_page + 1) % TOTAL_PAGES;
      osDelay(50); // Software debounce delay
    }
    last_btn_state = current_btn_state;

    if (!gyro_healthy)
    {
      OLED_ShowString(0, 0, (uint8_t *)"GYRO NOT READY  ");
      OLED_ShowString(0, 16, (uint8_t *)"MOTION DISABLED ");
      OLED_ShowString(0, 32, (uint8_t *)"CHECK I2C/POWER ");
      OLED_ShowString(0, 48, (uint8_t *)"POWER CYCLE CAR ");
      OLED_Refresh_Gram();
      osDelay(20);
      continue;
    }

    if (display_page == 0)
    {
    	// --- PAGE 0: Yaw, Target, Speeds, and CMD ---
		snprintf(line, sizeof(line), "Yaw: %-11.1f", (double)total_angle);
		OLED_ShowString(0, 0, (uint8_t *)line);

		snprintf(line, sizeof(line), "Tgt: %-11d", (int)arc_target_angle);
		OLED_ShowString(0, 16, (uint8_t *)line);

		snprintf(line, sizeof(line), "A:%5d B:%5d", (int)delta_a, (int)delta_b);
		OLED_ShowString(0, 32, (uint8_t *)line);

		snprintf(line, sizeof(line), "CMD: %-11s", uart_cmd_to_string());
		OLED_ShowString(0, 48, (uint8_t *)line);
	}
    else if (display_page == 1)
    {
		// --- PAGE 1: Ultrasonic, IR mV/Status, and IR Distances ---

		// Line 1 ($y = 0): Ultrasonic Distance
		snprintf(line, sizeof(line), "US Dist: %3d cm    ", (int)echo_debug);
		OLED_ShowString(0, 0, (uint8_t *)line);

		// Line 2 ($y = 16): IR0 Millivolts and Status
		snprintf(line, sizeof(line), "L:%4umV [%d]   ", ir0_mV, ir0_obs);
		OLED_ShowString(0, 16, (uint8_t *)line);

		// Line 3 ($y = 32): IR1 Millivolts and Status
		snprintf(line, sizeof(line), "R:%4umV [%d]   ", ir1_mV, ir1_obs);
		OLED_ShowString(0, 32, (uint8_t *)line);

		// Line 4 ($y = 48): Calculated Distances for both IR sensors
		snprintf(line, sizeof(line), "L:%dcm R:%dcm   ", (int)ir0_distance_cm, (int)ir1_distance_cm);
		OLED_ShowString(0, 48, (uint8_t *)line);
    }

    OLED_Refresh_Gram();
    osDelay(20); //was 100
  }
  /* USER CODE END oledTask */
}

/* USER CODE BEGIN Header_motorTask */
/**
 * @brief Function implementing the Motor_Taskl thread.
 * @param argument: Not used
 * @retval None
 */
/* USER CODE END Header_motorTask */
void motorTask(void const * argument)
{
  /* USER CODE BEGIN motorTask */

  /*--------- SERVO ---------------- */
  HAL_TIM_PWM_Start(&htim12, TIM_CHANNEL_2);

  //    osDelay(3000);
  set_servo_center();
  //    osDelay(3000);

  /* DC MOTOR */
  // both generate PWM signal

  // MOTORA Start PWM
  HAL_TIM_PWM_Start(&htim4, TIM_CHANNEL_3); // PB8 -> IN2
  HAL_TIM_PWM_Start(&htim4, TIM_CHANNEL_4); // PB9 -> IN1

  // MOTORB Start PWM
  HAL_TIM_PWM_Start(&htim9, TIM_CHANNEL_1); //
  HAL_TIM_PWM_Start(&htim9, TIM_CHANNEL_2); //

  motor_brake(); // start safe
                 /* Infinite loop */
  char command_line[sizeof(pending_cmd_buf)];
  for (;;)
  {
    if (pending_cmd_ready)
    {
      uint32_t primask = __get_PRIMASK();
      __disable_irq();
      memcpy(command_line, pending_cmd_buf, sizeof(command_line));
      pending_cmd_ready = 0U;
      if (primask == 0U)
        __enable_irq();

      command_line[sizeof(command_line) - 1U] = '\0';
      for (size_t index = 0U; command_line[index] != '\0'; ++index)
      {
        if (command_line[index] >= 'A' && command_line[index] <= 'Z')
          command_line[index] = (char)(command_line[index] - 'A' + 'a');
        if (command_line[index] == ';' || command_line[index] == ',')
          command_line[index] = ' ';
      }

      parse_and_enqueue_script(command_line);
      if (uart_cmd == CMD_NONE && !abort_now)
        (void)start_next_from_queue();
    }

    /* Every motion mode depends on valid heading feedback. Never continue a
     * command with a failed or stale gyro. */
    if (uart_cmd != CMD_NONE && uart_cmd != CMD_STOP)
    {
      const uint32_t now = HAL_GetTick();
      const bool stale = gyro_healthy &&
                         ((uint32_t)(now - gyro_last_good_tick) >
                          GYRO_STALE_TIMEOUT_MS);

      if (!gyro_healthy || stale)
      {
        Telemetry_RecordFault(stale ? "GYRO_STALE" : "GYRO_NOT_READY");
        abort_now = 1U;
      }
    }


    // emergency-stop
    if (abort_now)
    {

    	const int interrupted_command = (int)uart_cmd;

		abort_now = 0;
		obstacle_stop_mode = OBST_MODE_NONE;
		odom_counts_run = 0;
		odom_cm_run = 0.0f;
		odom_counts_run_ir = 0;
		odom_cm_run_ir = 0;
		slide_mode = SLIDE_NONE;
		slide_phase = SP_NONE;

		motor_brake();
		next_start_tick = 0;

		// luther centering
		if (is_turn_command(interrupted_command))
		{
			center_servo_after_turn(interrupted_command);
		}
		else
		{
			set_servo_center();
		}

		// reset distance/PID state if you want clean restart
		target_counts = 0;

		// clear outstanding script
		cmdq_clear();

		uart_cmd = CMD_NONE;
		turn_motor_enable_tick = 0;
		arc_postforward_cm = 0;
		stop_turn_controller();


		/* luther
		 * Send the reset acknowledgement if UART3 is available.
		 * static keeps the buffer valid during interrupt transmission.
		 */
		const char rst_message[] = "RST\r\n";

		if (!uart3_tx_busy)
		{
			uart3_tx_busy = 1;

			if (HAL_UART_Transmit_IT(
					&huart3,
					(uint8_t *)rst_message,
					sizeof(rst_message) - 1) != HAL_OK)
			{
				/* Transmission did not start, so release the busy flag. */
				uart3_tx_busy = 0;
			}
		}

		osDelay(5);

		/* Skip normal motor processing and restart the motor loop. */
		continue;

    }

    switch (uart_cmd)
    {
    case CMD_FORWARD:
    case CMD_REVERSE:
    {
      // ====== Tunables (keep Ki small if no anti-windup) ======
      //          const int   base_pwm = PWM_RUN;     // e.g., 4000
      const float Kp = 0.003f; // 0.05
      const float Ki = 0.003f; // 0.003        // start smaller without anti-windup
      const float Kd = 0.000f; // 0.001

      // best run kp=0.3, ki=0.003, kd=0.001
      // new best run kp = 0.003, ki = 0.003, kd = 0
      //  ====== Persistent PID state ======
      static int32_t i_acc = 0;
      static int32_t prev_err = 0;
      static float cpsA_f = 0.0f;
      static float cpsB_f = 0.0f;

      // ====== Distance stop using average counts ======
      uint16_t now_a = (uint16_t)__HAL_TIM_GET_COUNTER(&htim2);
      uint16_t now_b = (uint16_t)__HAL_TIM_GET_COUNTER(&htim3);

      int32_t moved_a = (int16_t)(now_a - enc_start_a);
      int32_t moved_b = -(int16_t)(now_b - enc_start_b); // right reversed
      int32_t avg_moved = (moved_a + moved_b) / 2;

      // ====== Stop conditions ======
      bool done_by_counts = false;
      if (target_counts >= 0)
      {
        done_by_counts = (avg_moved >= target_counts);
      }
      else
      {
        done_by_counts = (avg_moved <= target_counts);
      }

      bool done_by_obst = false;
      if (uart_cmd == CMD_FORWARD && obstacle_stop_mode != OBST_MODE_NONE)
      {
        switch (obstacle_stop_mode)
        {

        case OBST_MODE_US_T:
          // Stop condition for FUxx: ultrasound <= per-move threshold
          done_by_obst = (echo_debug <= us_stop_cm);

          // If extremely close, reverse only if allowed (FU), otherwise just stop (FX)
          if (echo_debug <= OBSTACLE_REV_CM && us_allow_reverse)
          {

            // Optional: send an immediate “collision-close” marker (like your US mode)
            if (!uart3_tx_busy)
            {
              char us_msg[32];
              int n = snprintf(us_msg, sizeof(us_msg), "us0.0,%d\n", (int)echo_debug);
              uart3_tx_busy = 1;
              HAL_UART_Transmit_IT(&huart3, (uint8_t *)us_msg, (uint16_t)n);
            }

            // Keep heading straight; hand over to reverse controller
            target_angle = arc_target_angle;
            set_servo_center();

            obstacle_stop_mode = OBST_MODE_US_BACK; // reuse your existing reverse-clear mode
            target_counts = INT32_MIN + 1;          // sentinel: counts won’t finish it

            // Clean PID handover
            i_acc = 0;
            prev_err = 0;

            done_by_obst = false; // we’re not finishing here; switching to REVERSE
            seg_rebase = 1;
            uart_cmd = CMD_REVERSE;
          }
          break;

        case OBST_MODE_US:
          // ultrasound: stop when we are closer than threshold
          done_by_obst = (echo_debug <= OBSTACLE_STOP_CM);
          // reverse

          if (echo_debug <= OBSTACLE_REV_CM)
          { // reverse bump

            if (!uart3_tx_busy)
            {
              char us_msg[32];
              int n = snprintf(us_msg, sizeof(us_msg), "us0.0,%d\n",
                               (int)echo_debug);
              uart3_tx_busy = 1;
              HAL_UART_Transmit_IT(&huart3, (uint8_t *)us_msg, (uint16_t)n);
            }

            // Keep heading straight
            target_angle = arc_target_angle;
            set_servo_center();

            // --- switch to reverse-until-clear mode ---
            //						  odom_counts_run = 0;                  // track how far we reverse
            obstacle_stop_mode = OBST_MODE_US_BACK;
            target_counts = INT32_MIN + 1; // sentinel so counts never end us

            // Clean PID handover
            i_acc = 0;
            prev_err = 0;

            done_by_obst = false;
            seg_rebase = 1; // <--- rebase on entry
            uart_cmd = CMD_REVERSE;
          }
          break;
        case OBST_MODE_IR_RIGHT:
          // FIR semantics: keep moving UNTIL right-IR says "no obstacle" (0)
          // -> stop when ir1_obs == 0
          done_by_obst = (ir1_obs == 0); // PC1
          break;
        case OBST_MODE_IR_LEFT:
          done_by_obst = (ir0_obs == 0); // PC0
          break;

        case OBST_MODE_IR_RIGHT_O: // NEW firo (stop when obstacle IS present)
          done_by_obst = (ir1_obs == 1);
          break;

        case OBST_MODE_IR_LEFT_O: // NEW filo (stop when obstacle IS present)
          done_by_obst = (ir0_obs == 1);
          break;
        default:
          break;
        }
      }

      if (uart_cmd == CMD_REVERSE && obstacle_stop_mode == OBST_MODE_US_BACK)
      {
        done_by_obst = (echo_debug >= US_BACK_CLEAR_CM);
      }

      // transmit US distance travelled and detected
      if (done_by_obst && (obstacle_stop_mode == OBST_MODE_US || obstacle_stop_mode == OBST_MODE_US_T))
      {
        odom_cm_run = (float)odom_counts_run / COUNTS_PER_CM;

        if (!uart3_tx_busy)
        {
          char us_msg[32];
          int n = snprintf(us_msg, sizeof(us_msg), "us%.1f,%d\n",
                           (double)odom_cm_run, (int)echo_debug);
          uart3_tx_busy = 1;
          HAL_UART_Transmit_IT(&huart3, (uint8_t *)us_msg, (uint16_t)n);
        }
      }

      // transmit IR distance travelled
      if (done_by_obst && (obstacle_stop_mode == OBST_MODE_IR_RIGHT || obstacle_stop_mode == OBST_MODE_IR_LEFT))
      {
        odom_cm_run_ir = (float)odom_counts_run_ir / COUNTS_PER_CM;

        if (!uart3_tx_busy)
        {
          char ir_msg[32];
          int n = snprintf(ir_msg, sizeof(ir_msg), "ir%.1f\n", (double)odom_cm_run_ir);
          uart3_tx_busy = 1;
          HAL_UART_Transmit_IT(&huart3, (uint8_t *)ir_msg, (uint16_t)n);
        }
      }

      if (done_by_counts || done_by_obst)
      {
        motor_brake();
        obstacle_stop_mode = OBST_MODE_NONE; // clear mode
        i_acc = 0;
        prev_err = 0; // reset PID state
        // send_ack_one_cmd();    // commented out (RYAN TOLD TO)
        uart_cmd = CMD_NONE;
        next_start_tick = HAL_GetTick() + INTER_CMD_MS;
        break;
      }

      // ====== Wheel speeds (counts per second) @ ~10 ms ======
      static uint16_t last_a = 0, last_b = 0;
      static uint32_t last_t = 0;
      uint32_t t = HAL_GetTick();

      if (last_t == 0)
      {
        last_t = t;
        last_a = now_a;
        last_b = now_b;
      }

      // If a new segment just started, rebase baselines and skip this tick’s accumulation
      if (seg_rebase)
      {
        last_a = now_a;
        last_b = now_b;
        last_t = t;
        seg_rebase = 0;

        // optional: also clear PID transients to avoid a kick
        i_acc = 0;
        prev_err = 0;
        cpsA_f = 0.0f;
        cpsB_f = 0.0f;

        // Do NOT compute da/db or update odometers this tick
      }

      int16_t da = (int16_t)(now_a - last_a);
      int16_t db = (int16_t)(now_b - last_b);
      db = -db; // keep right reversed consistently

      // record distance travelled during US/FIR/FIL movement
      if (uart_cmd == CMD_FORWARD && (obstacle_stop_mode == OBST_MODE_US || obstacle_stop_mode == OBST_MODE_US_T))
      {
        int32_t inc_counts = ((int32_t)da + (int32_t)db) / 2;
        odom_counts_run += inc_counts;
      }

      if (uart_cmd == CMD_FORWARD && (obstacle_stop_mode == OBST_MODE_IR_RIGHT || obstacle_stop_mode == OBST_MODE_IR_LEFT))
      {
        int32_t inc_counts = ((int32_t)da + (int32_t)db) / 2;
        odom_counts_run_ir += inc_counts;
      }

      uint32_t dt_ms = (t - last_t);
      if (dt_ms == 0)
        dt_ms = 1;

      int32_t cpsA = (int32_t)da * 1000 / (int32_t)dt_ms;
      int32_t cpsB = (int32_t)db * 1000 / (int32_t)dt_ms;

      // ---- Low-pass filter for PID feedback ----
      //static float cpsA_f = 0.0f, cpsB_f = 0.0f; // filtered cps
      float dt_s = (float)dt_ms / 1000.0f;
      float alpha = dt_s / (SPEED_LPF_TAU + dt_s); // 0<alpha<1, automatic with your dt

      cpsA_f += alpha * ((float)cpsA - cpsA_f);
      cpsB_f += alpha * ((float)cpsB - cpsB_f);

      last_a = now_a;
      last_b = now_b;
      last_t = t;

      //          // ====== Plain PID on speed difference ===== // SOMETHING WRONG HERE?
      //          int32_t err = (int32_t)(cpsA_f - cpsB_f); //filtered values
      ////          int32_t err = (cpsA - cpsB);

      // ====== Plain PID on speed difference WITH GYRO FEEDBACK =====
      // Speed-based error (motor balance)
      int32_t speed_err = (int32_t)(cpsA_f - cpsB_f); // filtered values

      // Calculate heading error BEFORE using it for gyro feedback
      error_angle = target_angle - total_angle;

      /* Wheel PI balances encoder speeds. Heading is corrected by the servo
       * below. Feeding yaw into both loops makes them fight each other. */
      int32_t err = speed_err;

      i_acc += err;
      const int32_t IACC_CLAMP = 25000;
      if (i_acc > IACC_CLAMP)
        i_acc = IACC_CLAMP;
      if (i_acc < -IACC_CLAMP)
        i_acc = -IACC_CLAMP;

      int32_t d = err - prev_err;
      prev_err = err;

      float off_f = Kp * (float)err + Ki * (float)i_acc + Kd * (float)d;
      int off = (int)off_f;
      //int off = 0;

      // luther speed
      int base = PWM_RUN;

      /*
       * Select a separate feed-forward calibration depending on direction.
       * This is evaluated here because an obstacle command may have changed
       * CMD_FORWARD into CMD_REVERSE earlier in this same loop iteration.
       */
      const bool is_reverse = (uart_cmd == CMD_REVERSE);

      const float left_compare_scale =
          is_reverse
              ? REV_LEFT_COMPARE_SCALE
              : FWD_LEFT_COMPARE_SCALE;

      const float right_compare_scale =
          is_reverse
              ? REV_RIGHT_COMPARE_SCALE
              : FWD_RIGHT_COMPARE_SCALE;

      int base_L =
          (int)((float)base * left_compare_scale + 0.5f);

      int base_R =
          (int)((float)base * right_compare_scale + 0.5f);

      int lDuty;
      int rDuty;

      if (!is_reverse)
      {
          /*
           * Larger compare = less power.
           * Positive off slows left and speeds up right.
           */
          lDuty = base_L + off;
          rDuty = base_R - off;
      }
      else
      {
          /*
           * Encoder speeds are negative in reverse, so the correction
           * direction must be inverted.
           */
          lDuty = base_L - off;
          rDuty = base_R + off;
      }

      lDuty = clamp_pwm_compare(lDuty);
      rDuty = clamp_pwm_compare(rDuty);

      // Hold the heading captured at the start of THIS straight segment.
      error_angle = target_angle - total_angle;

      // Tune K_SERVO if needed.
      // Make steering a bit gentler and ignore tiny gyro noise

      // adding servo deadband here

      const float K_SERVO = 1.5f; // was 3.5f; lower = less twitchy

      // Deadband: ignore tiny heading error (< 0.3°) to prevent servo hunting
      //			if (error_angle > -0.1f && error_angle < 0.1f) {
      //				error_angle = 0.0;
      //			}

      //int corr = (int)(K_SERVO * error_angle);
      /// added servo deadband here

      // luther turning
      float steering_error = error_angle;

      /* Prevent correction from reacting to tiny gyro noise. */
      if (fabsf(steering_error) < 0.3f)
      {
          steering_error = 0.0f;
      }

      float corr_f = K_SERVO * steering_error;

      int corr = (corr_f >= 0.0f)
                   ? (int)(corr_f + 0.5f)
                   : (int)(corr_f - 0.5f);

      /* Start from the centre established by the previous turn. */
      int servo = (int)current_center_ccr;

      /*if (uart_cmd == CMD_FORWARD)
      {
        if (error_angle > 0)
        {
          servo = SERVO_CENTER_AFTERRIGHT_CCR;
        }

        else if (error_angle < 0)
        {
          servo = SERVO_CENTER_AFTERLEFT_CCR; //160
        }
      }
      else if (uart_cmd == CMD_REVERSE)
      {
        if (error_angle < 0)
        {
          servo = SERVO_CENTER_AFTERRIGHT_CCR;
        }

        else if (error_angle > 0)
        {
          servo = SERVO_CENTER_AFTERLEFT_CCR;
        }
      }*/

      if (uart_cmd == CMD_FORWARD)
      {
        servo = servo - corr; // left is smaller CCR for your servo map
      }
      else
      {                       // CMD_REVERSE
        servo = servo + corr; // flip sense in reverse
      }

      // clamp to safe range
      if (servo < SERVO_LEFT_CCR)
        servo = SERVO_LEFT_CCR;
      if (servo > SERVO_RIGHT_CCR)
        servo = SERVO_RIGHT_CCR;

      straight_left_pwm = lDuty;
      straight_right_pwm = rDuty;
      straight_servo_ccr = servo;

      // add sliding right
      // === Slide state machine overrides servo while active ===
      if (slide_mode != SLIDE_NONE)
      {

        if (slide_phase == SP_TURN_OUT)
        {
          // steer toward target side until reaching ±45° from origin
          htim12.Instance->CCR2 = (slide_mode == SLIDE_RIGHT) ? SERVO_SLIDERIGHT_CCR : SERVO_SLIDELEFT_CCR;

          if (slide_mode == SLIDE_RIGHT)
          {
            // Right slide -> steer right, so LEFT is outer, RIGHT is inner
            int outer = (int)(SLIDE_OUTER_PWM);
            int inner = (int)(SLIDE_INNER_PWM);
            left_forward_duty(outer);
            right_forward_duty(inner);
          }
          else
          { // SLIDE_LEFT
            // Left slide -> steer left, so RIGHT is outer, LEFT is inner
            int outer = (int)(SLIDE_OUTER_PWM);
            int inner = (int)(SLIDE_INNER_PWM);
            right_forward_duty(outer);
            left_forward_duty(inner);
          }
          if ((slide_mode == SLIDE_RIGHT && total_angle <= arc_target_angle) ||
              (slide_mode == SLIDE_LEFT && total_angle >= arc_target_angle))
          {
            slide_phase = SP_TURN_IN; // start coming back
          }
        }
        else if (slide_phase == SP_TURN_IN)
        {
          // steer opposite side until we’re back at original heading (within tolerance)
          htim12.Instance->CCR2 = (slide_mode == SLIDE_RIGHT) ? SERVO_SLIDELEFT_CCR : SERVO_SLIDERIGHT_CCR;

          if (slide_mode == SLIDE_RIGHT)
          {
            // Coming back from right -> steer left, so RIGHT is outer now
            int outer = (int)(SLIDE_OUTER_PWM);
            int inner = (int)(SLIDE_INNER_PWM);
            right_forward_duty(outer);
            left_forward_duty(inner);
          }
          else
          { // SLIDE_LEFT
            // Coming back from left -> steer right, so LEFT is outer now
            int outer = (int)(SLIDE_OUTER_PWM);
            int inner = (int)(SLIDE_INNER_PWM);
            left_forward_duty(outer);
            right_forward_duty(inner);
          }
          arc_target_angle = slide_origin_heading;

          if ((slide_mode == SLIDE_RIGHT && total_angle >= arc_target_angle - 5.0) || // slide_return_heading
              (slide_mode == SLIDE_LEFT && total_angle <= arc_target_angle + 5.0))
          {
            const slide_t completed_slide = slide_mode;
            // done: hand back to your normal straight-line hold
            //						slide_phase = SP_RECENTER;
            slide_mode = SLIDE_NONE;
            slide_phase = SP_NONE; // complete sliding

            arc_target_angle = slide_origin_heading; // restore straight reference
            htim12.Instance->CCR2 = servo;           // normal correction resumes

            if (completed_slide == SLIDE_RIGHT)
            {
              set_servo_center_afterright();
            }


            if (completed_slide == SLIDE_LEFT)
            {
              set_servo_center_afterleft();
            }
            // braking logic, exit command
            motor_brake();
            obstacle_stop_mode = OBST_MODE_NONE; // clear mode
            i_acc = 0;
            prev_err = 0; // reset PID state
            uart_cmd = CMD_NONE;
            next_start_tick = HAL_GetTick() + INTER_CMD_MS;
            //
          }

          //				} else if (slide_phase == SP_RECENTER){
          //					//do like the first phase
          //					htim12.Instance->CCR2 = (slide_mode == SLIDE_RIGHT) ? SERVO_SLIDERIGHT_CCR : SERVO_SLIDELEFT_CCR;
          //
          //					if (slide_mode == SLIDE_RIGHT) {
          //						// Right slide -> steer right, so LEFT is outer, RIGHT is inner
          //						int outer = (int)(SLIDE_OUTER_PWM);
          //						int inner = (int)(SLIDE_INNER_PWM);
          //						left_forward_duty(outer);
          //						right_forward_duty(inner);
          //					} else { // SLIDE_LEFT
          //						// Left slide -> steer left, so RIGHT is outer, LEFT is inner
          //						int outer = (int)(SLIDE_OUTER_PWM);
          //						int inner = (int)(SLIDE_INNER_PWM);
          //						right_forward_duty(outer);
          //						left_forward_duty(inner);
          //					   }
          //					if ((slide_mode == SLIDE_RIGHT && total_angle <= arc_target_angle) ||
          //						(slide_mode == SLIDE_LEFT  && total_angle >= arc_target_angle)) {
          //							slide_mode = SLIDE_NONE;
          //							slide_phase = SP_NONE;   // complete sliding
          //
          //							arc_target_angle = slide_origin_heading;   // restore straight reference
          //							htim12.Instance->CCR2 = servo;             // normal correction resumes
          //
          //							//braking logic, exit command
          //							motor_brake();
          //							obstacle_stop_mode = OBST_MODE_NONE;   // clear mode
          //							i_acc = 0; prev_err = 0;               // reset PID state
          //							uart_cmd = CMD_NONE;
          //							next_start_tick = HAL_GetTick() + INTER_CMD_MS;
          //						}
        }
        else
        {
          // safety fallback
          htim12.Instance->CCR2 = servo;
        }
      }
      else
      { // no servoslide mode
        // no slide: normal straight correction
        htim12.Instance->CCR2 = servo;
    	//htim12.Instance->CCR2 = SERVO_CENTER_CCR; luther

      }

      //			htim12.Instance->CCR2 = servo;

      if (uart_cmd == CMD_FORWARD && slide_mode == SLIDE_NONE)
      {
        // Left motor (TIM4: CH3=IN2, CH4=IN1)
        __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_3, lDuty);
        __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_4, PWM_MAX);
        // Right motor (TIM9: CH1=IN2, CH2=IN1)
      //  __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_1, rDuty * 0.94); // 0.930
        __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_1, rDuty); //test

        __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_2, PWM_MAX);
      }
      else if (uart_cmd == CMD_REVERSE)
      { // CMD_REVERSE
        __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_3, PWM_MAX);
        __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_4, lDuty);
        __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_1, PWM_MAX);
       // __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_2, rDuty * 1.025); // 0.940
        __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_2, rDuty); // test

      }

      break;
    }

    // luther turn start
    case CMD_ARC_RIGHT:
    case CMD_ARC_LEFT:
    case CMD_ARC_RIGHT_REV:
    case CMD_ARC_LEFT_REV:
    {
      const int command = (int)uart_cmd;
      const uint32_t now = HAL_GetTick();

      /* Safety: a lifted/stalled robot has no yaw feedback and must not run forever. */
      if (turn_timeout_tick != 0U &&
          (int32_t)(now - turn_timeout_tick) >= 0)
      {
        motor_brake();
        Telemetry_RecordFault("TURN_TIMEOUT");
        abort_now = 1U;
        break;
      }

      /* Let the steering servo reach its requested angle before driving. */
      if (turn_motor_enable_tick != 0U &&
          (int32_t)(now - turn_motor_enable_tick) < 0)
      {
        motor_brake();
        turn_effort_cmd = 0.0f;
        turn_left_pwm = PWM_MAX;
        turn_right_pwm = PWM_MAX;
        break;
      }
      turn_motor_enable_tick = 0U;

      if (turn_control_phase == TURN_CTRL_IDLE)
        reset_turn_controller();

      const float direction = turn_yaw_direction(command);
      const float signed_error = arc_target_angle - total_angle;
      const float remaining = direction * signed_error;
      const float closing_rate = direction * gyro_yaw_rate_dps;

      turn_error_deg = signed_error;

      /*
       * After braking, wait for mechanical motion to stop before deciding
       * whether the command is complete or needs one gentle re-approach.
       */
      if (turn_control_phase == TURN_CTRL_SETTLE)
      {
        motor_brake();
        turn_effort_cmd = 0.0f;
        turn_left_pwm = PWM_MAX;
        turn_right_pwm = PWM_MAX;

        if ((int32_t)(now - turn_settle_until_tick) < 0)
          break;

        if (fabsf(signed_error) <= TURN_FINISH_TOL_DEG ||
            remaining <= 0.0f ||
            turn_approach_count >= TURN_MAX_APPROACHES)
        {
          finish_turn_command(command);
          break;
        }

        /* Stopped short: restore steering and make a slower approach. */
        turn_approach_count++;
        turn_i_error_deg_s = 0.0f;
        turn_pid_last_tick = now;
        turn_control_phase = TURN_CTRL_DRIVE;
        set_turn_servo_for_command(command);
        turn_motor_enable_tick = now + TURN_RETRY_SERVO_MS;
        break;
      }

      /*
       * Predict motion during sensing + braking delay. At 100 deg/s and
       * 45 ms look-ahead this begins braking about 4.5 degrees early.
       */
      const float positive_closing_rate = (closing_rate > 0.0f) ? closing_rate : 0.0f;
      const float brake_margin = TURN_FINISH_TOL_DEG +
                                 TURN_BRAKE_LOOKAHEAD_S * positive_closing_rate;

      if (remaining <= brake_margin)
      {
        motor_brake();
        center_servo_after_turn(command);
        turn_effort_cmd = 0.0f;
        turn_left_pwm = PWM_MAX;
        turn_right_pwm = PWM_MAX;
        turn_control_phase = TURN_CTRL_SETTLE;
        turn_settle_until_tick = now + TURN_SETTLE_MS;
        break;
      }

      float dt_s = (float)(now - turn_pid_last_tick) * 0.001f;
      if (dt_s < 0.001f)
        dt_s = 0.001f;
      if (dt_s > 0.050f)
        dt_s = 0.050f;
      turn_pid_last_tick = now;

      float candidate_i = turn_i_error_deg_s + remaining * dt_s;
      if (candidate_i > TURN_I_LIMIT_DEG_S)
        candidate_i = TURN_I_LIMIT_DEG_S;
      if (candidate_i < -TURN_I_LIMIT_DEG_S)
        candidate_i = -TURN_I_LIMIT_DEG_S;

      float effort = TURN_KP_EFFORT_PER_DEG * remaining +
                     TURN_KI_EFFORT_PER_DEG_S * candidate_i -
                     TURN_KD_EFFORT_PER_DPS * closing_rate;

      /* Conditional integration prevents wind-up while output is saturated. */
      if (effort < TURN_OUTER_EFFORT_MAX)
        turn_i_error_deg_s = candidate_i;

      if (effort > TURN_OUTER_EFFORT_MAX)
        effort = TURN_OUTER_EFFORT_MAX;
      if (effort < TURN_OUTER_EFFORT_MIN)
        effort = TURN_OUTER_EFFORT_MIN;

      const float inner_ratio = is_right_steer_turn(command)
                                  ? TURN_INNER_EFFORT_RATIO_R
                                  : TURN_INNER_EFFORT_RATIO_L;

      const int outer_pwm = pwm_compare_from_effort(effort);
      const int inner_pwm = pwm_compare_from_effort(effort * inner_ratio);

      turn_effort_cmd = effort;
      drive_turn_wheels(command, outer_pwm, inner_pwm);
      break;
    } // luther turn end

    case CMD_STOP:
      motor_brake();
      uart_cmd = CMD_NONE;
      next_start_tick = HAL_GetTick() + SLIDE_CMD_MS;

      break;

    case CMD_NONE:
    default:
    {
      if (!cmdq_empty())
      {
        if (HAL_GetTick() >= next_start_tick)
        {
          if (!start_next_from_queue())
          {
            // queue emptied right here -> ACK script finished
            //		                send_ack();
          }
        }
      }
      else
      {
        // idle with empty queue: make sure next_start_tick doesn’t block future scripts
        next_start_tick = 0;
      }
      break;
    }
    }
    osDelay(5);
  }
  /* USER CODE END motorTask */
}

/* USER CODE BEGIN Header_encoderTask */
/**
 * @brief Function implementing the Encoder_Task thread.
 * @param argument: Not used
 * @retval None
 */
/* USER CODE END Header_encoderTask */
void encoderTask(void const * argument)
{
  /* USER CODE BEGIN encoderTask */
  HAL_TIM_Encoder_Start(&htim2, TIM_CHANNEL_ALL); // encoder a
  HAL_TIM_Encoder_Start(&htim3, TIM_CHANNEL_ALL); // encoder b

  uint16_t last_a = (uint16_t)__HAL_TIM_GET_COUNTER(&htim2); // get the last count of encoderA
  uint16_t last_b = (uint16_t)__HAL_TIM_GET_COUNTER(&htim3);
  uint32_t last_tick = HAL_GetTick(); // get last time

  for (;;)
  {
	  uint32_t sample_tick = HAL_GetTick();
	  if ((sample_tick - last_tick) >= 20U) // nominal 50 Hz
		  {
			uint32_t elapsed_ms = sample_tick - last_tick;
			uint16_t sample_dt_ms = (elapsed_ms > UINT16_MAX)
			                          ? UINT16_MAX
			                          : (uint16_t)elapsed_ms;
			// ---- Encoder A (TIM2) ----
			uint16_t now_a = (uint16_t)__HAL_TIM_GET_COUNTER(&htim2);
			delta_a = (int16_t)(now_a - last_a);
			last_a = now_a;

			// ---- Encoder B (TIM3) ----
			uint16_t now_b = (uint16_t)__HAL_TIM_GET_COUNTER(&htim3);
			delta_b = (int16_t)(now_b - last_b);
			delta_b = -delta_b;
			last_b = now_b;

			/* Do not use += 20 here. After a delayed task that causes rapid
			 * catch-up samples and false speed spikes. */
			last_tick = sample_tick;


			// luther telementry
				Telemetry_SendEncoder(
				    (int16_t)delta_a,
				    (int16_t)delta_b,
				    (uart_cmd != CMD_NONE) ? 1U : 0U,
				    sample_dt_ms
				);

				Telemetry_SendTurn(
				    total_angle,
				    arc_target_angle,
				    gyro_yaw_rate_dps,
				    turn_error_deg,
				    turn_effort_cmd,
				    turn_left_pwm,
				    turn_right_pwm,
				    (uint8_t)turn_control_phase,
				    is_turn_command((int)uart_cmd) ? 1U : 0U
				);

				Telemetry_SendStraight(
				    total_angle,
				    target_angle,
				    gyro_yaw_rate_dps,
				    error_angle,
				    straight_servo_ccr,
				    straight_left_pwm,
				    straight_right_pwm,
				    (uart_cmd == CMD_FORWARD || uart_cmd == CMD_REVERSE) ? 1U : 0U
				);
			  }
//    if ((HAL_GetTick() - last_tick) >= 1000U) // 1 s window
//    {
//      // ---- Encoder A (TIM2) ----
//      uint16_t now_a = (uint16_t)__HAL_TIM_GET_COUNTER(&htim2);
//      delta_a = (int16_t)(now_a - last_a); // signed, wrap-safe
//      last_a = now_a;
//
//      // ---- Encoder B (TIM3) ----
//      uint16_t now_b = (uint16_t)__HAL_TIM_GET_COUNTER(&htim3);
//      delta_b = (int16_t)(now_b - last_b); // signed, wrap-safe
//      delta_b = -delta_b;
//      last_b = now_b;
//      last_tick += 1000U;

      //                // if you only want magnitude of counts in 1s: no direction
      //                int16_t speed_cps = (delta >= 0) ? delta : -delta; // counts per second

      // show either signed delta or magnitude:

      //                char buf[32];
      //                int n = snprintf(buf, sizeof(buf), "%ld,%ld\n", (int)delta_a, (long)delta_b);
      //				HAL_UART_Transmit(&huart3, (uint8_t*)buf, (uint16_t)n, 5);

    osDelay(1);
  }
  /* USER CODE END encoderTask */
}

/* USER CODE BEGIN Header_gyroTask */
/**
 * @brief Function implementing the Gyro_Task thread.
 * @param argument: Not used
 * @retval None
 */
/* USER CODE END Header_gyroTask */
void gyroTask(void const * argument)
{
  /* USER CODE BEGIN gyroTask */

  //	gyroInit();
  //
  //	    // --- Warm-up & initial bias (longer, steadier) ---
  //	    // Keep board still for 2–3 s if you can.
  //	    double sum = 0.0;
  //	    const int N = 300;   // 300 * 10 ms ~ 3 s
  //	    osDelay(50);
  //	    for (int i = 0; i < N; ++i) {
  //	        uint8_t v[2];
  //	        readByte(0x37, v);
  //	        int16_t raw = (int16_t)((v[0] << 8) | v[1]);
  //	        sum += (double)raw;
  //	        osDelay(10);
  //	    }
  //	    gyro_bias_dps = (sum / N) / 16.4;   // raw->dps
  //	    bias_locked = 0; // allow slow online trims
  //
  //	    // --- 100 Hz loop with trapezoid integration ---
  //	    TickType_t t0 = xTaskGetTickCount();
  //	    const TickType_t PERIOD = pdMS_TO_TICKS(10); // 10 ms
  //	    double prev_wz_dps = 0.0;
  //
  //	    for(;;) {
  //	        osDelay(10);
  //
  //	        uint8_t v[2];
  //	        readByte(0x37, v);                  // Z_H, Z_L
  //	        int16_t raw = (int16_t)((v[0] << 8) | v[1]);
  //
  //	        double wz_dps = ((double)raw / 16.4) - gyro_bias_dps;
  //
  //	        // trapezoid integration (dt = 0.01 s)
  //	        total_angle += 0.5 * (prev_wz_dps + wz_dps) * 0.01;
  //	        prev_wz_dps = wz_dps;
  //
  //	        // keep bounded
  //	        if (total_angle > 360.0) total_angle -= 360.0;
  //	        else if (total_angle < -360.0) total_angle += 360.0;
  //
  //	        // --- Online bias trim when we are surely stationary ---
  //	        // Use your encoders to detect standstill and a very small measured rate.
  //	        // This slowly corrects temperature drift while parked/idle.
  //	        if (!bias_locked) {
  //	            // counts per second estimate already computed elsewhere every 10ms; here we do a light version:
  //	            // if both wheels barely move and wz small, nudge bias.
  //	            if ((fabs(wz_dps) < 0.6) && (abs(delta_a) < 2) && (abs(delta_b) < 2)) {
  //	                // EWMA toward current reading -> drives bias so that wz→0 at standstill
  //	                // very slow adaptation so it won't corrupt while moving
  //	                gyro_bias_dps = 0.9995*gyro_bias_dps + 0.0005*((double)raw/16.4);
  //	            }
  //	        }
  //	    }

  GyroSafe gyro = {0};

  for (;;)
  {
    gyro_healthy = 0U;
    gyro_yaw_rate_dps = 0.0f;

    if (!GyroSafe_Recover(&gyro, &hi2c2))
    {
      Telemetry_RecordFault("GYRO_INIT");
      osDelay(GYRO_RETRY_DELAY_MS);
      continue;
    }

    /* Keep the robot completely still for this approximately two-second
     * calibration. Any failed sample rejects the whole calibration. */
    if (!GyroSafe_Calibrate(&gyro, 200U, GYRO_PERIOD_MS))
    {
      Telemetry_RecordFault("GYRO_CAL");
      osDelay(GYRO_RETRY_DELAY_MS);
      continue;
    }

    gyro_bias_dps = gyro.bias_raw / 16.4f;

    /* Heading cannot be reconstructed across a sensor failure, so rebase it
     * after a successful recovery. motorTask prevents motion while unhealthy. */
    total_angle = 0.0f;
    target_angle = 0.0f;
    arc_target_angle = 0.0f;

    uint32_t tick = HAL_GetTick();
    float previous_rate_dps = 0.0f;
    uint8_t consecutive_failures = 0U;

    gyro_last_good_tick = tick;
    gyro_healthy = 1U;

    for (;;)
    {
      float rate_dps;
      osDelay(GYRO_PERIOD_MS);

      if (!GyroSafe_ReadRateDps(&gyro, GYRO_SCALE_TRIM, &rate_dps))
      {
        consecutive_failures++;
        if (consecutive_failures >= GYRO_MAX_CONSECUTIVE_FAILURES)
        {
          gyro_healthy = 0U;
          gyro_yaw_rate_dps = 0.0f;
          Telemetry_RecordFault("GYRO_I2C");
          break;
        }
        continue;
      }

      consecutive_failures = 0U;

      uint32_t now = HAL_GetTick();
      float dt_s = (float)(now - tick) * 0.001f;
      tick = now;
      gyro_last_good_tick = now;

      if (dt_s > 0.050f)
        dt_s = 0.050f;

      if (fabsf(rate_dps) < GYRO_RATE_DEADBAND_DPS)
        rate_dps = 0.0f;

      total_angle += 0.5f * (previous_rate_dps + rate_dps) * dt_s;
      previous_rate_dps = rate_dps;
      gyro_yaw_rate_dps = rate_dps;
    }

    osDelay(GYRO_RETRY_DELAY_MS);
  }
  /* USER CODE END gyroTask */
}

/* USER CODE BEGIN Header_ultrasoundTask */
/**
 * @brief Function implementing the Ultrasound_Task thread.
 * @param argument: Not used
 * @retval None
 */
/* USER CODE END Header_ultrasoundTask */
void ultrasoundTask(void const * argument)
{
  /* USER CODE BEGIN ultrasoundTask */
  HAL_TIM_IC_Start_IT(&htim8, TIM_CHANNEL_2); // ✅ Start TIM8 input capture

  for (;;)
  {
	//HCSR04_Trigger();
    HCSR04_Trigger_10us();              // send trigger pulse
                                   //    	HCSR04_Trigger_10us();
    new_measurement_ready = false; // reset flag

    // wait until ISR sets the flag
    while (!new_measurement_ready)
    {
      osDelay(1);
    }

    // here, 'distance' has been updated in the callback
    osDelay(60); // wait ~200 ms before next measurement -> changed
  }
  /* USER CODE END ultrasoundTask */
}

/* USER CODE BEGIN Header_irTask */
/**
 * @brief Function implementing the IR_Task thread.
 * @param argument: Not used
 * @retval None
 */
/* USER CODE END Header_irTask */
void irTask(void const * argument)
{
  /* USER CODE BEGIN irTask */
  /* Infinite loop */
  // EMA smoothing for display & threshold stability
  const float alpha = 0.20f; // 0..1; higher = faster
  float v0 = 0.0f, v1 = 0.0f;

  // IR return a raw value that i convert to voltage
  // above voltage threshold = obstacle detected
  for (;;)
  {
    // Read latest DMA samples (16-bit reads are atomic on M4)
    uint16_t r0 = ir_adc[0];
    uint16_t r1 = ir_adc[1];

    // Convert to volts
    float f0 = 3.3f * (float)r0 / 4095.0f;
    float f1 = 3.3f * (float)r1 / 4095.0f;

    // Smooth
    v0 = (1.0f - alpha) * v0 + alpha * f0;
    v1 = (1.0f - alpha) * v1 + alpha * f1;

    // Publish for OLED (volatile globals)
    ir0_raw = r0;
    ir1_raw = r1;
    ir0_v = v0;
    ir1_v = v1;

    // Calculate real-time distance using the curve-fit formula
    ir0_distance_cm = Voltage_To_Distance_CM(v0);
    ir1_distance_cm = Voltage_To_Distance_CM(v1);

    // Simple obstacle flags (tune IR_VOLT_OBS)
    ir0_obs = (v0 >= IR_VOLT_OBS);
    ir1_obs = (v1 >= IR_VOLT_OBS);

    osDelay(10);
  }
  /* USER CODE END irTask */
}

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
