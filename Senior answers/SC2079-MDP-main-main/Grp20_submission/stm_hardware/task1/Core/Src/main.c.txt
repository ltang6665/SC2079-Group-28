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
#include "stdbool.h"
#include <string.h>
#include <stdlib.h>
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
I2C_HandleTypeDef hi2c2;

TIM_HandleTypeDef htim2;
TIM_HandleTypeDef htim3;
TIM_HandleTypeDef htim4;
TIM_HandleTypeDef htim8;
TIM_HandleTypeDef htim9;
TIM_HandleTypeDef htim12;

UART_HandleTypeDef huart3;

osThreadId LED_TaskHandle;
osThreadId OLED_TaskHandle;
osThreadId Motor_TaskHandle;
osThreadId Encoder_TaskHandle;
osThreadId Gyro_TaskHandle;
osThreadId Ultrasound_TaskHandle;
/* USER CODE BEGIN PV */
//osMutexId oledMutexHandle;

volatile float tc1 = 0, tc2 = 0, echo = 0;
//debugging ultrasound
volatile uint32_t echo_debug = 0;
volatile float distance = 0;
volatile float ir_distance_cm = 0.0f;
volatile bool new_measurement_ready = false;

volatile uint8_t obstacle_stop_mode = 0;      // 0=off, 1=on for bare 'F'

//encoder
volatile int delta_a = 0;
volatile int delta_b = 0;

//osMutexId oledMutexHandle;


volatile uint8_t abort_now = 0; //emergency stop, reset

volatile uint8_t rx_byte;              // single-byte RX (interrupt)

volatile uint8_t gyro_cal_request = 0;

volatile enum {
  CMD_NONE, CMD_FORWARD, CMD_REVERSE, CMD_STOP,
  CMD_ARC_RIGHT, CMD_ARC_LEFT,
  CMD_ARC_RIGHT_REV, CMD_ARC_LEFT_REV,
  CMD_CALIBRATE
} uart_cmd;

static char cmd_buf[256]; //cmd buffer length
static uint8_t cmd_idx = 0;

volatile uint32_t next_start_tick = 0;   // when we’re allowed to start the next cmd

/* -------- Script command queue -------- */
typedef enum {
  SCMD_NONE=0,
  SCMD_FWD_CM,      // value = centimeters (positive)
  SCMD_REV_CM,      // value = centimeters (positive)
  SCMD_ARC_FR,      // value = degrees  (90..360)
  SCMD_ARC_FL,
  SCMD_ARC_RR,
  SCMD_ARC_RL,
  SCMD_STOP,
  SCMD_EOS,
  SCMD_CALIBRATE
} script_cmd_t;

typedef struct {
  script_cmd_t type;
  int          value;   // deg or cm depending on type
} script_item_t;

#define CMDQ_CAP 32 //max number of commands i set to 32 (32-1)
static volatile script_item_t cmdq[CMDQ_CAP];
static volatile uint8_t q_head = 0, q_tail = 0;

static inline int cmdq_empty(void) { return q_head == q_tail; }
static inline int cmdq_full(void)  { return (uint8_t)(q_tail + 1) % CMDQ_CAP == q_head; }

static int cmdq_push(script_item_t it) {
  uint8_t next = (uint8_t)(q_tail + 1) % CMDQ_CAP;
  if (next == q_head) return 0;
  cmdq[q_tail] = it;
  q_tail = next;
  return 1;
}

static int cmdq_pop(script_item_t *out) {
  if (cmdq_empty()) return 0;
  *out = cmdq[q_head];
  q_head = (uint8_t)(q_head + 1) % CMDQ_CAP;
  return 1;
}


static inline uint8_t cmdq_count(void) {
  return (q_tail >= q_head) ? (q_tail - q_head) : (CMDQ_CAP - q_head + q_tail);
}

static inline void cmdq_clear(void) {
  __disable_irq();
  q_head = q_tail = 0;
  __enable_irq();
}

/* Ack helper */

static volatile uint8_t uart3_tx_busy = 0;
void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart){
    if (huart->Instance == USART3) uart3_tx_busy = 0;
}

static void send_ack(void) {
    static const uint8_t msg[] = "OK\n";
    if (uart3_tx_busy) return;                  // or queue it
    uart3_tx_busy = 1;
    (void)HAL_UART_Transmit_IT(&huart3, (uint8_t*)msg, sizeof(msg)-1);
    cmdq_clear();
}

//to send after each command
static void send_ack_one_cmd(void) {
    static const uint8_t msg[] = "done\n";
    if (uart3_tx_busy) return;                  // or queue it
    uart3_tx_busy = 1;
    (void)HAL_UART_Transmit_IT(&huart3, (uint8_t*)msg, sizeof(msg)-1);
}


// ---- Distance control state ----
volatile uint16_t enc_start_a = 0, enc_start_b = 0;
volatile int32_t  target_counts = 0;           // +ve forward, -ve reverse

#define WHEEL_DIAM_CM     5.7f //was 6.0
#define ENC_PPR           330
#define ENC_MODE_X4       4
#define ENC_CPR           (ENC_PPR * ENC_MODE_X4)

#define WHEEL_CIRC_CM     (3.14159f * WHEEL_DIAM_CM)
#define COUNTS_PER_CM     ((float)ENC_CPR / WHEEL_CIRC_CM)

#define PWM_MAX 7199
#define PWM_RUN 4600  // your current "run" duty
#define PWM_MIN 6800
#define PWM_INNER 6000

/* --- Gyro turn target & tuning --- */
volatile double arc_target_angle = 0;
#define ARC_DEG_TOL     2.00f          // 2 is good for left turn, 2.6 good for right turn
#define ARC_BASE_PWM    5400   // 5400 / 5000       // base duty for the driven (outer) wheel
#define ARC_MIN_DUTY    6000         // don’t let the driven wheel go too slow

// How much slower the inner wheel is vs outer during a turn.
#define LEFT_TURN_INNER_SCALE   1.1f
#define RIGHT_TURN_INNER_SCALE   1.1f

// to coast, set this to 0
// to brake, set this to 2

#define INTER_CMD_MS  800        // tweak 80–200ms, is the delay for inbetween commands
#define TURN_DELAY_LEFT 100 //
#define TURN_DELAY_RIGHT 100 //9.7 x 31.1
#define TURN_DELAY 50

// --- Steering mode (no angles; tokens like "fr", "fl") ---
typedef enum { TURN_NONE = 0, TURN_LEFT, TURN_RIGHT } turn_t;
volatile turn_t cmd_turn = TURN_NONE;

//    calibrated servo CCRs:
//    htim12.Instance->CCR2 = 230; // extreme right
//    osDelay(3000);
//    htim12.Instance->CCR2 = 180; // half right
//    htim12.Instance->CCR2 = 120; // half left
//    osDelay(3000);
//    htim12.Instance->CCR2 = 100; // extreme left
#define SERVO_CENTER_CCR   154  // straight (you already use ~152) /155
#define SERVO_CENTER_AFTERLEFT_CCR   154 // 161
#define SERVO_CENTER_AFTERRIGHT_CCR   154 //148
#define SERVO_RIGHT_CCR    250  // <-- set to your "forward-right" CCR
#define SERVO_LEFT_CCR     107	// <-- set to your "forward-left"  CCR
#define SERVO_REVERSE_LEFT_CCR 107 // 112 12x34 // 105 for indoor
#define SERVO_REVERSE_RIGHT_CCR 250 // 210 13.3x34 // 230 for indoor

// Optional: slow overall speed while turning to keep traction (0..1)
#define TURN_SPEED_FACTOR  1.15f

#define SPEED_LPF_TAU     0.05f   // ~0.2 s LPF for encoder speed

volatile double total_angle = 0.0;   // updated in gyroTask
volatile double target_angle = 0.0;  // locked when you start a straight move
volatile double error_angle  = 0.0;  // computed in motorTask
volatile double TURN_DEG = 90.0;

uint8_t ICMAddress = 0x68;
uint8_t gyroBuffer[20];

//gyro bias estimator & state
volatile double gyro_bias_dps = 0.0;
static double last_wz_dps = 0.0;
static uint8_t bias_locked = 0;

volatile uint32_t turn_motor_enable_tick = 0;  // when motors are allowed to start for turns

#define OBSTACLE_STOP_CM   30

volatile uint8_t arc_postforward_cm = 0;

//gyro scaling factor error?
volatile double GYRO_SCALE_TRIM = 0.989;  // start with 90/91 ≈ 0.989011
#define TURN_TRIM_LEFT   1.00f //0.989f   // ~ -1.1% if left overshoots 1°/90°
#define TURN_TRIM_RIGHT 1.0111f
#define TURN_TRIM_REV_LEFT
#define TURN_TRIM_REV_RIGHT

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_TIM4_Init(void);
static void MX_TIM2_Init(void);
static void MX_TIM3_Init(void);
static void MX_USART3_UART_Init(void);
static void MX_TIM9_Init(void);
static void MX_TIM12_Init(void);
static void MX_I2C2_Init(void);
static void MX_TIM8_Init(void);
void ledTask(void const * argument);
void oledTask(void const * argument);
void motorTask(void const * argument);
void encoderTask(void const * argument);
void gyroTask(void const * argument);
void ultrasoundTask(void const * argument);

/* USER CODE BEGIN PFP */

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */
//ultrasonic
float speedOfSound = 0.0343/2;

// ---- I2C helpers for ICM-20948 ----

// Replace your read/write helpers with these:

static inline bool icm_read(uint8_t reg, uint8_t *buf, uint16_t len) {
    if (HAL_I2C_Mem_Read(&hi2c2, ICMAddress<<1, reg, I2C_MEMADD_SIZE_8BIT,
                         buf, len, 2) == HAL_OK) return true;

    // Simple recovery
    HAL_I2C_DeInit(&hi2c2);
    if (HAL_I2C_Init(&hi2c2) != HAL_OK) return false;
    return false;
}

static inline bool icm_write(uint8_t reg, uint8_t val) {
    return HAL_I2C_Mem_Write(&hi2c2, ICMAddress<<1, reg, I2C_MEMADD_SIZE_8BIT,
                             &val, 1, 2) == HAL_OK;
}

// Read Z high/low in one go (explicit burst)
uint16_t icm_read_gz_raw(void) {
    uint8_t v[2];
    if (!icm_read(0x37, v, 2)) return 0; // handle error upstream
    return (uint16_t)((v[0] << 8) | v[1]);
}

void readByte(uint8_t addr, uint8_t *data) {
    gyroBuffer[0] = addr;
    HAL_I2C_Master_Transmit(&hi2c2, ICMAddress << 1, gyroBuffer, 1, 10);
    HAL_I2C_Master_Receive(&hi2c2, ICMAddress << 1, data, 2, 20);
}

void writeByte(uint8_t addr, uint8_t data) {
    gyroBuffer[0] = addr;
    gyroBuffer[1] = data;
    HAL_I2C_Master_Transmit(&hi2c2, ICMAddress << 1, gyroBuffer, 2, 20);
}

void gyroInit() {
    writeByte(0x06, 0x00);  osDelay(10);   // PWR_MGMT_1
    writeByte(0x03, 0x80);  osDelay(10);   // USER_CTRL reset
    writeByte(0x07, 0x07);  osDelay(10);   // PWR_MGMT_2
    writeByte(0x06, 0x01);  osDelay(10);   // PWR_MGMT_1 clock
    writeByte(0x7F, 0x20);  osDelay(10);   // BANK 2
    writeByte(0x01, 0x2F);  osDelay(10);   // GYRO_CONFIG_1 ±2000 dps

    writeByte(0x00, 0x11);  osDelay(10);   // GYRO_LPF, 20-30Hz, bump up if laggy (0x13/0x11)
    writeByte(0x7F, 0x00);  osDelay(10);   // BANK 0
    writeByte(0x07, 0x00);  osDelay(10);   // PWR_MGMT_2 enable

    //added this to see if can improve gyro
    // NO duty-cycling (make sure gyro never sleeps)
	// LP_CONFIG: [ACCEL_CYCLE|I2C_MST_CYCLE|GYRO_CYCLE] must be 0
	writeByte(0x05, 0x00);  osDelay(10);   // LP_CONFIG
	writeByte(0x06, 0x01);  osDelay(10);    // PWR_MGMT_1: CLKSEL=1 (PLL), SLEEP=0

}

static inline double wrap360(double x) {
    x = fmod(x, 360.0);
    if (x < 0) x += 360.0;
    return x;
}

// How much CW (right) is left to turn from cur to tgt, in [0,360)
static inline double cw_left(double cur, double tgt) {
    // If yaw increases CCW, CW deficit is (cur - tgt) mod 360
    double e = fmod(cur - tgt, 360.0);
    if (e < 0) e += 360.0;
    return e;
}

// How much CCW (left) is left to turn from cur to tgt, in [0,360)
static inline double ccw_left(double cur, double tgt) {
    // CCW deficit is (tgt - cur) mod 360
    double e = fmod(tgt - cur, 360.0);
    if (e < 0) e += 360.0;
    return e;
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

static inline void motor_brake(void)   // both high -> fast brake (your previous "stop")
{
  __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_3, PWM_MAX);
  __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_4, PWM_MAX);

  __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_1, PWM_MAX);
  __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_2, PWM_MAX);
}

static inline void left_forward_duty(int duty) {
  __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_3, duty);      // IN2 (PWM)
  __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_4, PWM_MAX);   // IN1 high -> FWD
}
static inline void right_forward_duty(int duty) {
  __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_1, duty);      // IN2 (PWM)
  __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_2, PWM_MAX);   // IN1 high -> FWD
}
static inline void left_coast(void) {
  __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_3, 0);
  __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_4, 0);
}
static inline void right_coast(void) {
  __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_1, 0);
  __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_2, 0);
}

static inline void left_reverse_duty(int duty) {
  // reverse on left: IN1 = PWM (CH4), IN2 = HIGH (CH3)
  __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_3, PWM_MAX);   // IN2 high
  __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_4, duty);      // IN1 pwm
}
static inline void right_reverse_duty(int duty) {
  // reverse on right: IN1 = PWM (CH2), IN2 = HIGH (CH1)
  __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_1, PWM_MAX);   // IN2 high
  __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_2, duty);      // IN1 pwm
}


static inline void set_servo_center(void) { htim12.Instance->CCR2 = SERVO_CENTER_CCR; }
static inline void set_servo_right(void)  { htim12.Instance->CCR2 = SERVO_RIGHT_CCR; }
static inline void set_servo_reverse_right(void)  { htim12.Instance->CCR2 = SERVO_REVERSE_RIGHT_CCR; }
static inline void set_servo_left(void)   { htim12.Instance->CCR2 = SERVO_LEFT_CCR;  }
static inline void set_servo_reverse_left(void)  { htim12.Instance->CCR2 = SERVO_REVERSE_LEFT_CCR; }
static inline void set_servo_center_afterleft(void)   { htim12.Instance->CCR2 = SERVO_CENTER_AFTERLEFT_CCR; }
static inline void set_servo_center_afterright(void)   { htim12.Instance->CCR2 = SERVO_CENTER_AFTERRIGHT_CCR; }


static const char *uart_cmd_to_string(void) {
    switch (uart_cmd) {
        case CMD_NONE:          return "NONE";
        case CMD_FORWARD:       return "FORWARD";
        case CMD_REVERSE:       return "REVERSE";
        case CMD_STOP:          return "STOP";
        case CMD_ARC_RIGHT:     return "ARC_RIGHT";
        case CMD_ARC_LEFT:      return "ARC_LEFT";
        case CMD_ARC_RIGHT_REV: return "ARC_RR";
        case CMD_ARC_LEFT_REV:  return "ARC_RL";
        default:                return "?";
    }
}


// to take a whole string of commands and break it up
static void parse_and_enqueue_script(char *line)
{
  // replace commas with spaces so strtok can split both
  for (char *p=line; *p; ++p) if (*p==',') *p = ' ';

  char *tok = strtok(line, " \t");
  while (tok) {

    if (strcmp(tok, "rst") == 0) {
	    abort_now = 1;             // handled in motorTask ASAP
	    // optional: drop the rest of the line
	    break;
	  }
    script_item_t it = { SCMD_NONE, 0 };

    // tokens already lowercased in Rx callback
    if      (tok[0]=='f' && tok[1]=='r') { it.type = SCMD_ARC_FR; it.value = atoi(&tok[2]); }
    else if (tok[0]=='f' && tok[1]=='l') { it.type = SCMD_ARC_FL; it.value = atoi(&tok[2]); }
    else if (tok[0]=='r' && tok[1]=='r') { it.type = SCMD_ARC_RR; it.value = atoi(&tok[2]); }
    else if (tok[0]=='r' && tok[1]=='l') { it.type = SCMD_ARC_RL; it.value = atoi(&tok[2]); }
    else if (tok[0]=='f')                { it.type = SCMD_FWD_CM; it.value = atoi(&tok[1]); }
    else if (tok[0]=='r')                { it.type = SCMD_REV_CM; it.value = atoi(&tok[1]); }
    else if (tok[0]=='s')                { it.type = SCMD_STOP;   it.value = 0;             }
    else if (tok[0]=='g')				 { it.type = SCMD_CALIBRATE, it.value = 0; 			}

    if (it.type != SCMD_NONE) {
      // Since we’re in an ISR callback when called from Rx, guard briefly
      //__disable_irq();
      int ok = cmdq_push(it);
      //__enable_irq();
      if (!ok) {
        const char emsg[] = "ERR:QUEUE\r\n";
//        HAL_UART_Transmit(&huart3,(uint8_t*)emsg,sizeof(emsg)-1,0xFFFF);
        // drop the rest if full
        break;
      }
    }
    tok = strtok(NULL, " \t");
  }
  script_item_t eos = { SCMD_EOS, 0 };
  (void)cmdq_push(eos);
}


// pop from queue and set all the variables needed, then change the uart_cmd
static int start_next_from_queue(void)
{
  script_item_t it;
  if (!cmdq_pop(&it)) return 0;

  switch (it.type) {
    case SCMD_FWD_CM: {
      int cm = it.value;
      enc_start_a = (uint16_t)__HAL_TIM_GET_COUNTER(&htim2);
	  enc_start_b = (uint16_t)__HAL_TIM_GET_COUNTER(&htim3);
	  target_angle  = total_angle;
	  set_servo_center();

	  if (cm > 0){
		  // normal distance move
		  int32_t tgt = (int32_t)(cm * COUNTS_PER_CM + 0.5f);
		  target_counts = tgt;
		  obstacle_stop_mode = 0;                  // ensure off
		  uart_cmd = CMD_FORWARD;
	  }
	  else{
		  // use ultrasound just go forward forever
		  obstacle_stop_mode = 1;
		  target_counts = INT32_MAX;               // sentinel; we won't use it
		  uart_cmd = CMD_FORWARD;
	  }
      return 1;
    }
    case SCMD_REV_CM: {
      int cm = (it.value > 0) ? it.value : 50;
      enc_start_a = (uint16_t)__HAL_TIM_GET_COUNTER(&htim2);
      enc_start_b = (uint16_t)__HAL_TIM_GET_COUNTER(&htim3);
      int32_t tgt = -(int32_t)(cm * COUNTS_PER_CM + 0.5f);
      target_counts = tgt;
      target_angle  = total_angle;
      set_servo_center();
      uart_cmd = CMD_REVERSE;
      return 1;
    }

    case SCMD_ARC_FR:
      TURN_DEG = (float)it.value;
      set_servo_right();
//      arc_target_angle = total_angle - (TURN_DEG * TURN_TRIM_RIGHT);   // CW = negative
      arc_target_angle = arc_target_angle - TURN_DEG;  // desired yaw
      turn_motor_enable_tick = HAL_GetTick() + TURN_DELAY_RIGHT;
      arc_postforward_cm = 0;
      uart_cmd = CMD_ARC_RIGHT;
      return 1;

    case SCMD_ARC_FL:
      TURN_DEG = (float)it.value;
      set_servo_left();
//      arc_target_angle = total_angle + (TURN_DEG * TURN_TRIM_LEFT);   // CCW = positive
      arc_target_angle = arc_target_angle + TURN_DEG;
      turn_motor_enable_tick = HAL_GetTick() + TURN_DELAY_LEFT;   // <-- add
      arc_postforward_cm = 0;
      uart_cmd = CMD_ARC_LEFT;
      return 1;

    case SCMD_ARC_RR:
      TURN_DEG = (float)it.value;
      set_servo_reverse_right();
//      arc_target_angle = total_angle + (TURN_DEG * TURN_TRIM_RIGHT);
      arc_target_angle = arc_target_angle + TURN_DEG;
      turn_motor_enable_tick = HAL_GetTick() + TURN_DELAY;   // <-- add
      arc_postforward_cm = 0;
      uart_cmd = CMD_ARC_RIGHT_REV;
      return 1;

    case SCMD_ARC_RL:
      TURN_DEG = (float)it.value;
      set_servo_reverse_left();
      arc_target_angle = arc_target_angle - TURN_DEG;
      turn_motor_enable_tick = HAL_GetTick() + TURN_DELAY;   // <-- add
      arc_postforward_cm = 0;
      uart_cmd = CMD_ARC_LEFT_REV;
      return 1;

    case SCMD_STOP:
      motor_brake();
      set_servo_center();
      uart_cmd = CMD_STOP;
      return 1;

    case SCMD_CALIBRATE:
    	motor_brake();
    	gyro_cal_request = 1;
    	uart_cmd = CMD_CALIBRATE;
    	return 1;

    case SCMD_EOS:
      send_ack();                   // <--- ACK the just-finished line
      // Do NOT set uart_cmd; just return. The idle loop will pick up the next item
	  return 1;

    default:
      break;
  }
  return 0;
}

//ultrasound



/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_TIM4_Init();
  MX_TIM2_Init();
  MX_TIM3_Init();
  MX_USART3_UART_Init();
  MX_TIM9_Init();
  MX_TIM12_Init();
  MX_I2C2_Init();
  MX_TIM8_Init();
  /* USER CODE BEGIN 2 */
  OLED_Init();


  /* Start byte-by-byte UART RX */
  HAL_UART_Receive_IT(&huart3, (uint8_t*)&rx_byte, 1);

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
  osThreadDef(OLED_Task, oledTask, osPriorityIdle, 0, 128);
  OLED_TaskHandle = osThreadCreate(osThread(OLED_Task), NULL);

  /* definition and creation of Motor_Task */
  osThreadDef(Motor_Task, motorTask, osPriorityAboveNormal, 0, 128);
  Motor_TaskHandle = osThreadCreate(osThread(Motor_Task), NULL);

  /* definition and creation of Encoder_Task */
  osThreadDef(Encoder_Task, encoderTask, osPriorityBelowNormal, 0, 128);
  Encoder_TaskHandle = osThreadCreate(osThread(Encoder_Task), NULL);

  /* definition and creation of Gyro_Task */
  osThreadDef(Gyro_Task, gyroTask, osPriorityNormal, 0, 128);
  Gyro_TaskHandle = osThreadCreate(osThread(Gyro_Task), NULL);

  /* definition and creation of Ultrasound_Task */
  osThreadDef(Ultrasound_Task, ultrasoundTask, osPriorityBelowNormal, 0, 128);
  Ultrasound_TaskHandle = osThreadCreate(osThread(Ultrasound_Task), NULL);

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
  __HAL_RCC_GPIOB_CLK_ENABLE();
  __HAL_RCC_GPIOD_CLK_ENABLE();
  __HAL_RCC_GPIOC_CLK_ENABLE();
  __HAL_RCC_GPIOA_CLK_ENABLE();

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

  /* USER CODE BEGIN MX_GPIO_Init_2 */

  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */
//callback function, when rxbuffer comes in, go to this function
// my callback function will parse the command

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

void HCSR04_Trigger(void) {
    HAL_GPIO_WritePin(US_Trig_GPIO_Port, US_Trig_Pin, GPIO_PIN_RESET);
    HAL_Delay(2);
    HAL_GPIO_WritePin(US_Trig_GPIO_Port, US_Trig_Pin, GPIO_PIN_SET);
    HAL_Delay(1); // Short delay for 10µs pulse
    HAL_GPIO_WritePin(US_Trig_GPIO_Port, US_Trig_Pin, GPIO_PIN_RESET);
}

void HAL_TIM_IC_CaptureCallback(TIM_HandleTypeDef *htim) {
	if (HAL_GPIO_ReadPin(GPIOC, GPIO_PIN_7) == GPIO_PIN_SET) {
	    tc1 = HAL_TIM_ReadCapturedValue(htim, TIM_CHANNEL_2);
	} else {
	    tc2 = HAL_TIM_ReadCapturedValue(htim, TIM_CHANNEL_2);
	    echo = (tc2 > tc1) ? (tc2 - tc1) : (65536 - tc1 + tc2);
	    echo_debug = echo;
	    echo_debug = (uint32_t) echo * (0.0343f / 2.0f);   // <-- distance updated here!
	    new_measurement_ready = true;
	}
}

//keep this callback short, just update the buffer and add to queue once \n
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART3) {
        uint8_t c = rx_byte;

        if (c == '\r' || c == '\n') {
            // finalize the line
            cmd_buf[cmd_idx] = '\0';

            if (cmd_idx > 0) {
                // normalize to lowercase (FR90 -> fr90)
                for (uint8_t i = 0; i < cmd_idx; i++) {
                    if (cmd_buf[i] >= 'A' && cmd_buf[i] <= 'Z') {
                        cmd_buf[i] = (char)(cmd_buf[i] - 'A' + 'a');
                    }
                    // optional just in case: also normalize delimiters here (comma/semicolon -> space)
                    if (cmd_buf[i] == ';' || cmd_buf[i] == ',') cmd_buf[i] = ' ';
                }

                // enqueue the whole script (e.g. "f50 r50 fr90 rr90")
                parse_and_enqueue_script(cmd_buf);

                // after parse_and_enqueue_script(cmd_buf);
//                char dbg[24];
//                snprintf(dbg, sizeof(dbg), "ENQ:%u\r\n", cmdq_count());
//                HAL_UART_Transmit(&huart3, (uint8_t*)dbg, strlen(dbg), 0xFFFF);

                // if we’re idle, start immediately
                if (uart_cmd == CMD_NONE) {
                    (void)start_next_from_queue();
                }
            }

            cmd_idx = 0;  // ready for the next line
        } else {
            // accumulate chars until newline, guard overflow
            if (cmd_idx < sizeof(cmd_buf) - 1) {
                cmd_buf[cmd_idx++] = (char)c;
            } else {
                // overflow -> drop this line
                cmd_idx = 0;
            }
        }

        // re-arm RX interrupt
        HAL_UART_Receive_IT(&huart3, (uint8_t*)&rx_byte, 1);
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
  for(;;)
  {
    //HAL_UART_Transmit(&huart3, (uint8_t*)&ch, 1, 0xFFFF); //every toggle STM will transmit ch out
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
//    uint8_t hello[20] = "Hello World!\0";
  /* Infinite loop */
	char line[32];

	    for(;;)
	    {
	        //osMutexWait(oledMutexHandle, osWaitForever);
//	    	if (gyro_cal_request == 1) {
//	    		snprintf(line, sizeof(line), "Gyro calibrating!");
//	    		OLED_ShowString(0, 0, (uint8_t*)line);
//	    	}

	        // Line 1: Yaw
	        snprintf(line, sizeof(line), "Yaw: %-6d", (int)total_angle);
//	        OLED_ShowString(0, 0, (uint8_t*)"                ");
	        OLED_ShowString(0, 0, (uint8_t*)line);

	        // Line 2: Speed A & B together
	        snprintf(line, sizeof(line), "A:%5d  B:%5d", (int)delta_a, (int)delta_b);

//          snprintf(line, sizeof(line), "Speed A:%5d", (int)delta_a);

//	        OLED_ShowString(0, 16, (uint8_t*)"                ");  // clear line
	        OLED_ShowString(0, 16, (uint8_t*)line);

	        snprintf(line, sizeof(line), "Tgt: %-6d", (int)arc_target_angle);

	        OLED_ShowString(0, 32, (int)line);

	        // Line 3: Distance
//	        snprintf(line, sizeof(line), "Dist: %5.1f cm", (double)distance_cm);
//	        OLED_ShowString(0, 32, (uint8_t*)"                ");
//	        OLED_ShowString(0, 32, (uint8_t*)line);
//
//	        snprintf(line, sizeof(line), "Dist: %3d", (int)echo_debug);
//	        OLED_ShowString(0, 32, (uint8_t*)"                ");
//	        OLED_ShowString(0, 32, (uint8_t*)line);

	        // Line 4: IR Distance
//	        snprintf(line, sizeof(line), "IR: %4.1f cm", ir_distance_cm);
//	        OLED_ShowString(0, 48, (uint8_t*)"                ");
//	        OLED_ShowString(0, 48, (uint8_t*)line);
////
//	        snprintf(line, sizeof(line), "CMD:%s", uart_cmd_to_string());
//	        OLED_ShowString(0, 48, (uint8_t*)"                ");  // clear the line
//	        OLED_ShowString(0, 48, (uint8_t*)line);

	        OLED_Refresh_Gram();
	        //osMutexRelease(oledMutexHandle);

	        osDelay(500); // update twice per second
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
    for (;;)
    {

      // emergency-stop
	  if (abort_now) {
		 abort_now = 0;
		 obstacle_stop_mode = 0;
		 motor_brake();
		 next_start_tick = 0;
		 set_servo_center();
		 // reset distance/PID state if you want clean restart
		 target_counts = 0;
		 // clear outstanding script
		 cmdq_clear();
		 uart_cmd = CMD_NONE;
		 turn_motor_enable_tick = 0;
		 arc_postforward_cm = 0;
		 const char k[] = "RST\r\n";
		 if (uart3_tx_busy) return;                  // or queue it
		 uart3_tx_busy = 1;
		 (void)HAL_UART_Transmit_IT(&huart3, (uint8_t*)k, sizeof(k)-1);
		 osDelay(5);
		 continue;   // skip normal control for this tick
	   }

      switch (uart_cmd)
      {
      case CMD_FORWARD:
      case CMD_REVERSE:
      {
          // ====== Tunables (keep Ki small if no anti-windup) ======
//          const int   base_pwm = PWM_RUN;     // e.g., 4000
          const float Kp = 0.003f;	//0.05
          const float Ki = 0.003f;   //0.003        // start smaller without anti-windup
          const float Kd = 0.000f;  //0.001

          //best run kp=0.3, ki=0.003, kd=0.001
          //new best run kp = 0.003, ki = 0.003, kd = 0
          // ====== Persistent PID state ======
          static int32_t i_acc = 0;
          static int32_t prev_err = 0;
          static uint8_t active_brake_ticks = 0;

          // ====== Distance stop using average counts ======
          uint16_t now_a = (uint16_t)__HAL_TIM_GET_COUNTER(&htim2);
          uint16_t now_b = (uint16_t)__HAL_TIM_GET_COUNTER(&htim3);

          int32_t moved_a = (int16_t)(now_a - enc_start_a);
          int32_t moved_b = - (int16_t)(now_b - enc_start_b); // right reversed
          int32_t avg_moved = (moved_a + moved_b) / 2;

          // ====== Stop conditions ======
          bool done_by_counts = false;
          if (target_counts >= 0) {
              done_by_counts = (avg_moved >= target_counts);
          } else {
              done_by_counts = (avg_moved <= target_counts);
          }

          bool done_by_ultra = false;
          // Only for forward and only when bare 'F' engaged:
          if (uart_cmd == CMD_FORWARD && obstacle_stop_mode) {
              // stop when we reach 15 cm
              done_by_ultra = (echo_debug <= OBSTACLE_STOP_CM);
          }


//          if (done_by_counts || done_by_ultra) {
//              motor_brake();
//              obstacle_stop_mode = 0;              // ADD: clear mode
//              i_acc = 0; prev_err = 0;             // reset PID state
//              send_ack_one_cmd();
//              uart_cmd = CMD_NONE;
//              next_start_tick = HAL_GetTick() + INTER_CMD_MS;
//              break;
//          }
          // --- STRONG ACTIVE BRAKING LOGIC ---
			if (done_by_counts || done_by_ultra || active_brake_ticks > 0) {

				// 1. First time hitting the target? Start the brake timer.
				if (active_brake_ticks == 0) {
					active_brake_ticks = 10; // 15 ticks * 5ms = 75ms of reverse power
				}

				// 2. Execute the active brake (STRONG KICK)
				if (active_brake_ticks > 1) {
					// We use a duty cycle of 2000 here.
					// Since PWM is inverted (7199 is off, 0 is max), 2000 provides a very strong burst!
					if (uart_cmd == CMD_FORWARD) {
						// Kick backwards to kill forward momentum
						__HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_3, PWM_MAX);
						__HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_4, 3500);
						__HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_1, PWM_MAX);
						__HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_2, 3500);
					} else {
						// Kick forwards to kill reverse momentum
						__HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_3, 3500);
						__HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_4, PWM_MAX);
						__HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_1, 3500);
						__HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_2, PWM_MAX);
					}
					active_brake_ticks--;
					break; // Skip the rest of the PID math for this tick!
				}

				// 3. Timer finished! Now come to a complete, dead stop.
				if (active_brake_ticks == 1) {
					motor_brake();          // Short circuit motors (holding brake)
					obstacle_stop_mode = 0; // Clear obstacle mode
					i_acc = 0; prev_err = 0;
					active_brake_ticks = 0; // Reset for the next movement

					send_ack_one_cmd();
					uart_cmd = CMD_NONE;
					next_start_tick = HAL_GetTick() + INTER_CMD_MS;
					break;
				}
			}

          // ====== Wheel speeds (counts per second) @ ~10 ms ======
          static uint16_t last_a = 0, last_b = 0;
          static uint32_t last_t = 0;
          uint32_t t = HAL_GetTick();
          if (last_t == 0) { last_t = t; last_a = now_a; last_b = now_b; }

          int16_t  da = (int16_t)(now_a - last_a);
          int16_t  db = (int16_t)(now_b - last_b);
          db = -db; // keep right reversed consistently

          uint32_t dt_ms = (t - last_t);
          if (dt_ms == 0) dt_ms = 1;

          int32_t cpsA = (int32_t)da * 1000 / (int32_t)dt_ms;
          int32_t cpsB = (int32_t)db * 1000 / (int32_t)dt_ms;

          // ---- Low-pass filter for PID feedback ----
          static float cpsA_f = 0.0f, cpsB_f = 0.0f;   // filtered cps
          float dt_s  = (float)dt_ms / 1000.0f;
          float alpha = dt_s / (SPEED_LPF_TAU + dt_s); // 0<alpha<1, automatic with your dt

          cpsA_f += alpha * ((float)cpsA - cpsA_f);
          cpsB_f += alpha * ((float)cpsB - cpsB_f);


          last_a = now_a; last_b = now_b; last_t = t;

          // ====== Plain PID on speed difference WITH GYRO FEEDBACK =====
          // Speed-based error (motor balance)
          int32_t speed_err = (int32_t)(cpsA_f - cpsB_f); //filtered values

          // Calculate heading error BEFORE using it for gyro feedback
          error_angle = target_angle - total_angle;

          // Gyro-based error (heading drift correction)
          // If drifting right (positive angle error), reduce right motor (positive off)
          // If drifting left (negative angle error), increase right motor (negative off)
          const float K_GYRO = 15.0f;  // tune: higher = more aggressive gyro correction
          int32_t gyro_err = (int32_t)(K_GYRO * error_angle);

          // Combined error for motor correction
          int32_t err = speed_err + gyro_err;

          i_acc   += err;                     // <- no anti-windup: integrate always
          //lets add anti wind up
//          const int32_t IACC_CLAMP = 25000;
//          if(i_acc > IACC_CLAMP) i_acc = IACC_CLAMP;
//          if(i_acc < -IACC_CLAMP) i_acc = -IACC_CLAMP;

          int32_t d = err - prev_err;
          prev_err = err;

          float off_f = Kp*(float)err + Ki*(float)i_acc + Kd*(float)d;
          int off = (int)off_f;

          // --- Base speed (allow a manual global scale later if you add it) ---
          int base = PWM_RUN;

          // --- Steering profile (no angle math) ---
          float scaleL = 1.0f, scaleR = 1.0f;
          int   base_turn = base;

          // --- Apply PID offset (if any) and steering scales ---
          int lDuty = (int)((base_turn - off) * scaleL);
          int rDuty = (int)((base_turn + off) * scaleR);

          //GYRO - servo control based on heading error
			// error_angle already calculated above in PID section
			// Proportional servo steering: stronger correction for better heading control
			const float K_SERVO = 4.5f;  // Increased from 1.0f for more responsive steering

			// Apply deadband to prevent servo hunting on small errors
			double servo_error = error_angle;
			if (servo_error > -0.5f && servo_error < 0.5f) {
				servo_error = 0.0f;  // Ignore very small errors
			}

			int servo_corr = (int)(K_SERVO * servo_error);
			int servo = SERVO_CENTER_CCR - servo_corr;  // Simple proportional control

			// For reverse, flip the correction sense
			if (uart_cmd == CMD_REVERSE) {
				servo = SERVO_CENTER_CCR + servo_corr;
			}

			// clamp to safe range
			if (servo < SERVO_LEFT_CCR)  servo = SERVO_LEFT_CCR;
			if (servo > SERVO_RIGHT_CCR) servo = SERVO_RIGHT_CCR;

			htim12.Instance->CCR2 = servo;

          if (uart_cmd == CMD_FORWARD) {
              // Left motor (TIM4: CH3=IN2, CH4=IN1)
              __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_3, lDuty);
              __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_4, PWM_MAX);
              // Right motor (TIM9: CH1=IN2, CH2=IN1)
              __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_1, rDuty * 0.95); //0.930
              __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_2, PWM_MAX);
          } else { // CMD_REVERSE
              __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_3, PWM_MAX);
              __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_4, lDuty);
              __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_1, PWM_MAX);
              __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_2, rDuty * 1.03); //0.940
          }

          break;
      }

		case CMD_ARC_RIGHT:
		case CMD_ARC_LEFT:
		  {

			  // Wait for servo to settle before engaging motors
			  if (turn_motor_enable_tick && HAL_GetTick() < turn_motor_enable_tick) {
				  motor_brake();          // or left_coast()/right_coast() if you prefer no brake
				  break;                  // skip motor drive this tick
			  }
			  turn_motor_enable_tick = 0; // one-shot; allow motor drive from now on
			  // --- Directional angular error on the circle ---


			  double err  = arc_target_angle - total_angle;
			  double aerr = (err >= 0.0) ? err : -err;
			  // --- Stop when close enough ---

			  //if (aerr < ARC_DEG_TOL)
			  if ((uart_cmd == CMD_ARC_RIGHT && total_angle <= arc_target_angle ) ||
			          (uart_cmd == CMD_ARC_LEFT  && total_angle >= arc_target_angle)) {
			      // left_coast();
			      // right_coast();
			      motor_brake();
			      if (uart_cmd == CMD_ARC_RIGHT) { set_servo_center_afterright(); }
			      else { set_servo_center_afterleft(); }

			      osDelay(300);

			      send_ack_one_cmd();

			      if (arc_postforward_cm > 0 && uart_cmd == CMD_ARC_RIGHT ) {
					  // Start a small forward move immediately (no queue)
					  enc_start_a = (uint16_t)__HAL_TIM_GET_COUNTER(&htim2);
					  enc_start_b = (uint16_t)__HAL_TIM_GET_COUNTER(&htim3);
					  target_counts = -(int32_t)(arc_postforward_cm * COUNTS_PER_CM + 0.5f);
					  target_angle  = total_angle;           // keep current heading
					  obstacle_stop_mode = 0;                // normal forward stop by counts
					  uart_cmd = CMD_REVERSE;                // hand over to distance controller
					  arc_postforward_cm = 0;
				  } else {
					  // Normal end of turn
					  uart_cmd = CMD_NONE;
					  next_start_tick = HAL_GetTick() + INTER_CMD_MS;
				  }

			      break;
			  }

			  // IMPORTANT: do NOT apply left-right speed PID offset here.
			  // We want a pivot-ish arc: outer drives, inner coasts.

			  if (uart_cmd == CMD_ARC_RIGHT) {
				  // turning right: left = outer (drive), right = inner (coast)

				  // --- Outer wheel speed schedule (slow down near target to avoid overshoot) ---
				  int outer = ARC_BASE_PWM;
				  if (aerr < 45.0) outer = (int)(1.0f * ARC_BASE_PWM); //1.05
				  if (aerr < 20.0) outer = (int)(1.0f * ARC_BASE_PWM); //1.1
				  if (outer > ARC_MIN_DUTY) outer = ARC_MIN_DUTY;
				  left_forward_duty(outer*1.07);

				  // --- Inner wheel behaviour
				  int inner = (int)(outer * RIGHT_TURN_INNER_SCALE);
//				  right_reverse_duty(inner); // tighter
//				  right_coast(); // coast turning
				  right_forward_duty(inner*1.15); // best turn 30x11.5 tried 1.15, 1.2

				  //inner faster wider turn

				  //add 1 cm forward 29x10

			  } else {
				  // turning left: right = outer (drive), left = inner (coast)

				  // --- Outer wheel speed schedule (slow down near target to avoid overshoot) ---
				  int outer = ARC_BASE_PWM;
				  if (aerr < 45.0) outer = (int)(1.0f* ARC_BASE_PWM);
				  if (aerr < 20.0) outer = (int)(1.0f * ARC_BASE_PWM);
				  if (outer > ARC_MIN_DUTY) outer = ARC_MIN_DUTY;
				  right_forward_duty(outer*1.07);

				  // --- Inner wheel behaviour
				  int inner = (int)(outer * LEFT_TURN_INNER_SCALE);
//				  left_reverse_duty(inner);
//				  left_coast();
				  left_forward_duty(inner * 1.15); // best turn 30x10.5 1.15

				  //add 2 cm forward 28x10

			  }

			  break;
		  }

		case CMD_ARC_RIGHT_REV:
		case CMD_ARC_LEFT_REV:
		{

			// Wait for servo to settle before engaging motors
		    if (turn_motor_enable_tick && HAL_GetTick() < turn_motor_enable_tick) {
			    motor_brake();          // or left_coast()/right_coast() if you prefer no brake
			    break;                  // skip motor drive this tick
		    }
		    turn_motor_enable_tick = 0; // one-shot; allow motor drive from now on

		    double err  = arc_target_angle - total_angle;
		    double aerr = (err >= 0) ? err : -err;

		    if ((uart_cmd == CMD_ARC_RIGHT_REV && total_angle >= arc_target_angle) ||
		    	(uart_cmd == CMD_ARC_LEFT_REV  && total_angle <= arc_target_angle)) {
		        motor_brake();
		        if (uart_cmd == CMD_ARC_RIGHT_REV) { set_servo_center_afterright(); }
		        else { set_servo_center_afterleft(); }

			    osDelay(400);

//			    send_ack_one_cmd();

		        if (arc_postforward_cm > 0 && uart_cmd == CMD_ARC_RIGHT_REV ) {
					  // Start a small forward move immediately (no queue)
					  enc_start_a = (uint16_t)__HAL_TIM_GET_COUNTER(&htim2);
					  enc_start_b = (uint16_t)__HAL_TIM_GET_COUNTER(&htim3);
					  target_counts = -(int32_t)(arc_postforward_cm * COUNTS_PER_CM + 0.5f);
					  target_angle  = total_angle;           // keep current heading
					  obstacle_stop_mode = 0;                // normal forward stop by counts
					  uart_cmd = CMD_REVERSE;                // hand over to distance controller
					  arc_postforward_cm = 0;                // one-shot consumed
					  // NOTE: do NOT set next_start_tick here; the FWD block will do it when done
				  } else if (arc_postforward_cm > 0 && uart_cmd == CMD_ARC_LEFT_REV ) {
					  // Start a small forward move immediately (no queue)
					  enc_start_a = (uint16_t)__HAL_TIM_GET_COUNTER(&htim2);
					  enc_start_b = (uint16_t)__HAL_TIM_GET_COUNTER(&htim3);
					  target_counts = -(int32_t)(arc_postforward_cm * COUNTS_PER_CM + 0.5f);
					  target_angle  = total_angle;           // keep current heading
					  obstacle_stop_mode = 0;                // normal forward stop by counts
					  uart_cmd = CMD_REVERSE;                // hand over to distance controller
					  arc_postforward_cm = 0;                // one-shot consumed
					  // NOTE: do NOT set next_start_tick here; the FWD block will do it when done
				  } else {
					  // Normal end of turn
					  uart_cmd = CMD_NONE;
					  next_start_tick = HAL_GetTick() + INTER_CMD_MS;
				  }
		        break;
		    }

		    int outer = ARC_BASE_PWM;
		    if (aerr < 45.0) outer = (int)(1.00f * ARC_BASE_PWM);
		    if (aerr < 20.0) outer = (int)(1.00f * ARC_BASE_PWM);
		    if (outer > ARC_MIN_DUTY) outer = ARC_MIN_DUTY;

		    // Reverse turns: drive only the OUTER wheel in REVERSE, inner coasts
		    if (uart_cmd == CMD_ARC_RIGHT_REV) {
		        // right turn => LEFT is outer
		        left_reverse_duty(outer * 1.07);       // outer runs in reverse

			    // --- Inner wheel behaviour
		        int inner = (int)(outer * RIGHT_TURN_INNER_SCALE);
//			    right_forward_duty(inner);
//			    right_coast();
			    right_reverse_duty(inner*1.15);

			    // 28.5cm x 6.5cm


		    } else {
		        // left turn => RIGHT is outer
		        right_reverse_duty(outer*1.07);      // outer runs in reverse

			    // --- Inner wheel behaviour
		        int inner = (int)(outer * LEFT_TURN_INNER_SCALE);
//			    left_forward_duty(inner);
//		        left_coast();
			    left_reverse_duty(inner*1.15);

			    // 28.3cm x 6.5cm
		    }
		    break;
		}
		case CMD_CALIBRATE:
			motor_brake();

			if (gyro_cal_request == 0) {
				send_ack_one_cmd();
				uart_cmd = CMD_NONE;
				next_start_tick = HAL_GetTick() + INTER_CMD_MS;
			}
			break;

		case CMD_STOP:
		  motor_brake();

		  send_ack_one_cmd();
		  uart_cmd = CMD_NONE;
		  next_start_tick = HAL_GetTick() + INTER_CMD_MS;

		  break;


		case CMD_NONE:
		default: {
		    if (!cmdq_empty()) {
		        if (HAL_GetTick() >= next_start_tick) {
		            if (!start_next_from_queue()) {
		                // queue emptied right here -> ACK script finished
//		                send_ack();
		            }
		        }
		    } else {
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
    HAL_TIM_Encoder_Start(&htim2, TIM_CHANNEL_ALL); //encoder a
    HAL_TIM_Encoder_Start(&htim3, TIM_CHANNEL_ALL); //encoder b

        uint16_t last_a = (uint16_t)__HAL_TIM_GET_COUNTER(&htim2); //get the last count of encoderA
        uint16_t last_b = (uint16_t)__HAL_TIM_GET_COUNTER(&htim3);
        uint32_t last_tick = HAL_GetTick(); // get last time
        char line[20];

        for (;;)
        {
            if ((HAL_GetTick() - last_tick) >= 1000U)   // 1 s window
            {
                // ---- Encoder A (TIM2) ----
                uint16_t now_a = (uint16_t)__HAL_TIM_GET_COUNTER(&htim2);
                delta_a = (int16_t)(now_a - last_a);   // signed, wrap-safe
                last_a = now_a;

                // ---- Encoder B (TIM3) ----
                uint16_t now_b = (uint16_t)__HAL_TIM_GET_COUNTER(&htim3);
                delta_b = (int16_t)(now_b - last_b);   // signed, wrap-safe
                delta_b = -delta_b;
                last_b = now_b;
                last_tick += 1000U;

//                // if you only want magnitude of counts in 1s: no direction
//                int16_t speed_cps = (delta >= 0) ? delta : -delta; // counts per second

                // show either signed delta or magnitude:


//                char buf[32];
//                int n = snprintf(buf, sizeof(buf), "%ld,%ld\n", (int)delta_a, (long)delta_b);
//				HAL_UART_Transmit(&huart3, (uint8_t*)buf, (uint16_t)n, 5);
            }
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
//	uint8_t  val[2] = {0,0};
//	int16_t  raw = 0;
//
//	// --- Collect bias while stationary ---
//	const int   N = 300;                 // ~3s at 10 ms
//	double      offset_raw = 0.0;
//	uint32_t    t_prev = HAL_GetTick();
//
//	// small settle
//	osDelay(50);
//
//	for (int n = 0; n < N; ++n) {
//		readByte(0x37, val);             // Z high/low
//		raw = (int16_t)((val[0] << 8) | val[1]);
//		offset_raw += (double)raw;
//		osDelay(10);
//	}
//	offset_raw /= (double)N;             // mean raw bias (counts)
//
//	// --- Integrate at ~100 Hz ---
//	double wz_prev_dps = 0.0;
//	t_prev = HAL_GetTick();
//
//	for (;;) {
//		osDelay(10);                     // ~100 Hz cadence
//
//		readByte(0x37, val);
//		raw = (int16_t)((val[0] << 8) | val[1]);
//
//		// Convert to dps using measured bias
//		double wz_dps = ((double)raw - offset_raw) / 16.4;
//
////		wz_dps *= GYRO_SCALE_TRIM;  // apply gain correction before integration
//
//		// Trapezoid integration with real dt
//		uint32_t t_now = HAL_GetTick();
//		double dt = (double)(t_now - t_prev) / 1000.0;   // seconds
//		if (dt > 0.0 && dt < 0.05) {
//			total_angle += 0.5 * (wz_prev_dps + wz_dps) * dt;
//		}
//		t_prev = t_now;
//		wz_prev_dps = wz_dps;
//	}

//oldway

//	    gyroInit();
//
//	    uint8_t val[2] = {0};
//	    int16_t angular_speed = 0;
//
//	    uint32_t tick = 0;
//	    double offset = 0;
//
//	    // ---- Calibration ----
//	    for (int i = 0; i < 100; i++) {
//	        osDelay(20);
//	        readByte(0x37, val);   // GYRO_ZOUT_H
//	        angular_speed = (int16_t)((val[0] << 8) | val[1]);
//	        offset += angular_speed;
//	    }
//	    offset /= 100.0;
//
//	    tick = HAL_GetTick();
//
//	    // ---- Main loop ----
//	    for (;;) {
//	    	if (gyro_cal_request == 1) {
//	    		double sum_speed = 0;
//
//	    		// take 100 samples, 2 secs to complete
//	    		for (int i = 0; i < 100; i++) {
//	    			osDelay(20);
//	    			readByte(0x37, val);
//	    			sum_speed += (int16_t)((val[0] << 8) | val[1]);
//	    		}
//
//	    		// apply new offset
//	    		offset = sum_speed / 100.0;
//
//	    		// reset all angles
//	    		total_angle = 0.0;
//	    		target_angle = 0.0;
//	    		arc_target_angle = 0.0;
//	    		tick = HAL_GetTick();
//
//	    		// signal motortask it is safe to move again
//	    		gyro_cal_request = 0;
//
//	    	}
//	        osDelay(20);
//
//	        readByte(0x37, val);   // GYRO_ZOUT_H
//	        angular_speed = (int16_t)((val[0] << 8) | val[1]);
//
//	        double velocity = (double)angular_speed - offset;
//
//	        // integrate to get total yaw angle
//	        if(fabs(velocity) > 8.0){
//	        	total_angle += ((double)angular_speed - offset) *
//	        		                       ((HAL_GetTick() - tick) / 16400.0);
//	        }
//
//	        // compute error vs target if needed
//	//        error_angle = target_angle - total_angle;
//
//	        tick = HAL_GetTick();
//	    }
	// --- 1. FULL HARDWARE RESET ---
	writeByte(0x06, 0x80); // PWR_MGMT_1: Set bit 7 to trigger Device Reset
	osDelay(100);          // CRITICAL: Give the silicon 100ms to reboot

	gyroInit();

	uint8_t val[2] = {0};
	int16_t angular_speed = 0;
	uint32_t tick = 0;
	double offset = 0;

	// --- 2. BOOT CALIBRATION (With Flush) ---
	// Throw away first 25 samples to let filters settle
	for (int i = 0; i < 25; i++) {
		osDelay(20);
		readByte(0x37, val);
	}
	// Take 100 clean samples
	for (int i = 0; i < 100; i++) {
		osDelay(20);
		readByte(0x37, val);   // GYRO_ZOUT_H
		angular_speed = (int16_t)((val[0] << 8) | val[1]);
		offset += angular_speed;
	}
	offset /= 100.0;

	tick = HAL_GetTick();

	// ---- Main loop ----
	for (;;) {

		// --- 3. ON-DEMAND CALIBRATION ('g') ---
		if (gyro_cal_request == 1) {
			double sum_speed = 0;

			// Throw away first 25 samples
			for (int i = 0; i < 25; i++) {
				osDelay(20);
				readByte(0x37, val);
			}

			// Take 100 clean samples (Takes exactly 2 seconds: 100 * 20ms)
			// (FIXED THE TYPO HERE!)
			for (int i = 0; i < 100; i++) {
				osDelay(20);
				readByte(0x37, val);
				sum_speed += (int16_t)((val[0] << 8) | val[1]);
			}

			// apply new offset
			offset = sum_speed / 100.0;

			// reset all angles
			total_angle = 0.0;
			target_angle = 0.0;
			arc_target_angle = 0.0;
			tick = HAL_GetTick();

			// signal motortask it is safe to move again
			gyro_cal_request = 0;
		}

		// --- 4. NORMAL INTEGRATION ---
		osDelay(20);

		readByte(0x37, val);   // GYRO_ZOUT_H
		angular_speed = (int16_t)((val[0] << 8) | val[1]);

		double velocity = (double)angular_speed - offset;

		// integrate to get total yaw angle (Deadband filter)
		if(fabs(velocity) > 8.0){
			total_angle += ((double)angular_speed - offset) *
						   ((HAL_GetTick() - tick) / 16400.0);
		}

		tick = HAL_GetTick();
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
    HAL_TIM_IC_Start_IT(&htim8, TIM_CHANNEL_2);  // ✅ Start TIM8 input capture

    for (;;)
    {
        HCSR04_Trigger();                         // send trigger pulse
        new_measurement_ready = false;            // reset flag

        // wait until ISR sets the flag
        while (!new_measurement_ready) {
            osDelay(1);
        }

        // here, 'distance' has been updated in the callback
        osDelay(200);  // wait ~200 ms before next measurement
    }
  /* USER CODE END ultrasoundTask */
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
