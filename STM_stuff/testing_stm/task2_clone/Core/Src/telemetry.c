#include "telemetry.h"

#include <stdio.h>
#include <string.h>

#define TELEMETRY_COMMAND_NAME_LEN 16
#define TELEMETRY_FAULT_CODE_LEN   20
#define WHEEL_PI_TELEMETRY_PERIOD_MS 40U
#define WHEEL_PI_MAX_AGE_MS 100U

static UART_HandleTypeDef *telemetry_uart = NULL;

static volatile uint32_t current_command_id = 0;
static volatile uint8_t command_pending = 0;
static char pending_command_name[TELEMETRY_COMMAND_NAME_LEN];
static volatile int pending_command_value = 0;
static volatile uint32_t pending_command_tick = 0;

static volatile uint8_t fault_pending = 0;
static volatile uint32_t pending_fault_tick = 0;
static char pending_fault_code[TELEMETRY_FAULT_CODE_LEN];

/* Straight-heading PID configuration. The gains are configured once from
 * main.c, then one SPID record is attached to every new command ID. */
static volatile float straight_pid_kp = 0.0f;
static volatile float straight_pid_ki = 0.0f;
static volatile float straight_pid_kd = 0.0f;

static volatile uint8_t straight_pid_configured = 0U;

/* One coherent controller update, not unrelated globals sampled at different times. */
typedef struct
{
    uint32_t command_id;
    uint32_t control_tick_ms;
    uint32_t control_dt_ms;
    float cps_a_filtered;
    float cps_b_filtered;
    int32_t speed_error;
    int32_t i_acc;
    int32_t i_limit;
    int applied_off;
    int drive_percent;
    int left_pwm;
    int right_pwm;
} WheelPiSnapshot;

static volatile WheelPiSnapshot wheel_pi_snapshot;
static volatile uint8_t wheel_pi_valid = 0U;
static uint8_t wheel_pi_sent = 0U;
static uint32_t wheel_pi_last_send_tick = 0U;


static int32_t scale_by_1000(float value)
{
    float scaled = value * 1000.0f;
    scaled += (scaled >= 0.0f) ? 0.5f : -0.5f;
    return (int32_t)scaled;
}


static void transmit_line(char *buffer, size_t size, int length)
{
    if (telemetry_uart == NULL || length <= 0 || length >= (int)size)
    {
        return;
    }

    (void)HAL_UART_Transmit(
        telemetry_uart,
        (uint8_t *)buffer,
        (uint16_t)length,
        20 /* bounded UART wait in EncoderTask; allow the longer WPI record */
    );
}


void Telemetry_Init(UART_HandleTypeDef *uart)
{
    telemetry_uart = uart;
    current_command_id = 0;
    command_pending = 0;
    fault_pending = 0;
    pending_command_name[0] = '\0';
    pending_fault_code[0] = '\0';
    wheel_pi_valid = 0U;
    wheel_pi_sent = 0U;
    wheel_pi_last_send_tick = 0U;

    straight_pid_kp = 0.0f;
    straight_pid_ki = 0.0f;
    straight_pid_kd = 0.0f;

    straight_pid_configured = 0U;
}

void Telemetry_SetStraightPidGains(float kp,float ki,float kd)
{
    const uint32_t primask = __get_PRIMASK();

    __disable_irq();

    straight_pid_kp = kp;
    straight_pid_ki = ki;
    straight_pid_kd = kd;

    straight_pid_configured = 1U;

    if (primask == 0U)
    {
        __enable_irq();
    }
}

void Telemetry_StartCommand(const char *command_name, int value)
{
    char temp_name[TELEMETRY_COMMAND_NAME_LEN];
    uint32_t primask;

    if (command_name == NULL)
    {
        return;
    }

    strncpy(temp_name, command_name, sizeof(temp_name) - 1U);
    temp_name[sizeof(temp_name) - 1U] = '\0';

    primask = __get_PRIMASK();
    __disable_irq();

    current_command_id++;
    wheel_pi_valid = 0U;
    wheel_pi_sent = 0U;
    pending_command_tick = HAL_GetTick();

    pending_command_value = value;
    memcpy(pending_command_name, temp_name, sizeof(pending_command_name));
    command_pending = 1U;

    if (primask == 0U)
    {
        __enable_irq();
    }
}


void Telemetry_RecordFault(const char *fault_code)
{
    char temp_code[TELEMETRY_FAULT_CODE_LEN];
    uint32_t primask;

    if (fault_code == NULL)
    {
        return;
    }

    strncpy(temp_code, fault_code, sizeof(temp_code) - 1U);
    temp_code[sizeof(temp_code) - 1U] = '\0';

    primask = __get_PRIMASK();
    __disable_irq();

    pending_fault_tick = HAL_GetTick();
    memcpy(pending_fault_code, temp_code, sizeof(pending_fault_code));
    fault_pending = 1U;

    if (primask == 0U)
    {
        __enable_irq();
    }
}


void Telemetry_ClearWheelPi(void)
{
    const uint32_t primask = __get_PRIMASK();
    __disable_irq();
    wheel_pi_valid = 0U;
    if (primask == 0U) __enable_irq();
}


void Telemetry_PublishWheelPi(
    uint32_t control_tick_ms, uint32_t control_dt_ms,
    float cps_a_filtered, float cps_b_filtered, int32_t speed_error,
    int32_t i_acc, int32_t i_limit, int applied_off, int drive_percent,
    int left_pwm, int right_pwm
)
{
    const uint32_t primask = __get_PRIMASK();
    __disable_irq();
    wheel_pi_snapshot.command_id = current_command_id;
    wheel_pi_snapshot.control_tick_ms = control_tick_ms;
    wheel_pi_snapshot.control_dt_ms = control_dt_ms;
    wheel_pi_snapshot.cps_a_filtered = cps_a_filtered;
    wheel_pi_snapshot.cps_b_filtered = cps_b_filtered;
    wheel_pi_snapshot.speed_error = speed_error;
    wheel_pi_snapshot.i_acc = i_acc;
    wheel_pi_snapshot.i_limit = i_limit;
    wheel_pi_snapshot.applied_off = applied_off;
    wheel_pi_snapshot.drive_percent = drive_percent;
    wheel_pi_snapshot.left_pwm = left_pwm;
    wheel_pi_snapshot.right_pwm = right_pwm;
    wheel_pi_valid = 1U;
    if (primask == 0U) __enable_irq();
}


void Telemetry_SendWheelPi(uint8_t straight_active)
{
    WheelPiSnapshot sample;
    const uint32_t now = HAL_GetTick();
    uint8_t valid;
    uint32_t active_id;
    uint32_t primask;

    if (telemetry_uart == NULL || !straight_active) return;
    if (wheel_pi_sent &&
        (uint32_t)(now - wheel_pi_last_send_tick) < WHEEL_PI_TELEMETRY_PERIOD_MS)
        return;

    primask = __get_PRIMASK();
    __disable_irq();
    valid = wheel_pi_valid;
    active_id = current_command_id;
    sample = wheel_pi_snapshot;
    if (primask == 0U) __enable_irq();

    if (!valid || sample.command_id == 0U || sample.command_id != active_id ||
        (uint32_t)(now - sample.control_tick_ms) > WHEEL_PI_MAX_AGE_MS)
        return;

    /* Rates are sent in thousandths of counts/s, like STR angles in millidegrees. */
    char buffer[192];
    const int length = snprintf(
        buffer, sizeof(buffer),
        "WPI,%lu,%lu,%lu,%lu,%ld,%ld,%ld,%ld,%ld,%d,%d,%d,%d\r\n",
        (unsigned long)now, (unsigned long)sample.command_id,
        (unsigned long)sample.control_tick_ms, (unsigned long)sample.control_dt_ms,
        (long)scale_by_1000(sample.cps_a_filtered),
        (long)scale_by_1000(sample.cps_b_filtered),
        (long)sample.speed_error, (long)sample.i_acc, (long)sample.i_limit,
        sample.applied_off, sample.drive_percent, sample.left_pwm, sample.right_pwm
    );
    transmit_line(buffer, sizeof(buffer), length);
    wheel_pi_last_send_tick = now;
    wheel_pi_sent = 1U;
}


void Telemetry_SendEncoder(
    int16_t motor_a,
    int16_t motor_b,
    uint8_t command_active,
    uint16_t sample_dt_ms
)
{
    uint32_t command_id;

    uint8_t send_command = 0U;
    uint8_t send_fault = 0U;
    uint8_t pid_configured = 0U;

    uint32_t command_tick = 0U;
    uint32_t fault_tick = 0U;

    int command_value = 0;

    float pid_kp = 0.0f;
    float pid_ki = 0.0f;
    float pid_kd = 0.0f;

    char command_name[TELEMETRY_COMMAND_NAME_LEN] = {0};
    char fault_code[TELEMETRY_FAULT_CODE_LEN] = {0};

    uint32_t primask;

    if (telemetry_uart == NULL)
    {
        return;
    }

    /*
     * Copy shared state while interrupts are briefly disabled.
     */
    primask = __get_PRIMASK();
    __disable_irq();

    command_id = current_command_id;

    if (command_pending)
    {
        send_command = 1U;

        command_tick = pending_command_tick;
        command_value = pending_command_value;

        memcpy(
            command_name,
            pending_command_name,
            sizeof(command_name)
        );

        /*
         * Take a snapshot of the PID gains belonging to
         * this command.
         */
        pid_configured = straight_pid_configured;

        pid_kp = straight_pid_kp;
        pid_ki = straight_pid_ki;
        pid_kd = straight_pid_kd;

        command_pending = 0U;
    }

    if (fault_pending)
    {
        send_fault = 1U;
        fault_tick = pending_fault_tick;

        memcpy(
            fault_code,
            pending_fault_code,
            sizeof(fault_code)
        );

        fault_pending = 0U;
    }

    if (primask == 0U)
    {
        __enable_irq();
    }

    /*
     * Existing command telemetry.
     */
    if (send_command)
    {
        char buffer[64];

        int length = snprintf(
            buffer,
            sizeof(buffer),

            "CMD,%lu,%lu,%s:%d\r\n",

            (unsigned long)command_id,
            (unsigned long)command_tick,
            command_name,
            command_value
        );

        transmit_line(
            buffer,
            sizeof(buffer),
            length
        );
    }

    /*
     * Send the PID gains once for the new command.
     *
     * Example:
     * SPID,52341,7,29200,0,2000
     *
     * means:
     * Kp = 29.2
     * Ki = 0.0
     * Kd = 2.0
     */
    if (send_command && pid_configured)
    {
        char buffer[96];

        int length = snprintf(
            buffer,
            sizeof(buffer),

            "SPID,%lu,%lu,%ld,%ld,%ld\r\n",

            (unsigned long)command_tick,
            (unsigned long)command_id,

            (long)scale_by_1000(pid_kp),
            (long)scale_by_1000(pid_ki),
            (long)scale_by_1000(pid_kd)
        );

        transmit_line(
            buffer,
            sizeof(buffer),
            length
        );
    }

    /*
     * Existing fault telemetry.
     */
    if (send_fault)
    {
        char buffer[64];

        int length = snprintf(
            buffer,
            sizeof(buffer),

            "FLT,%lu,%lu,%s\r\n",

            (unsigned long)fault_tick,
            (unsigned long)command_id,
            fault_code
        );

        transmit_line(
            buffer,
            sizeof(buffer),
            length
        );
    }

    /*
     * Existing encoder telemetry.
     */
    {
        uint32_t sample_command_id =
            command_active ? command_id : 0U;

        char buffer[72];

        int length = snprintf(
            buffer,
            sizeof(buffer),

            "ENC,%lu,%lu,%d,%d,%u\r\n",

            (unsigned long)HAL_GetTick(),
            (unsigned long)sample_command_id,

            (int)motor_a,
            (int)motor_b,

            (unsigned int)sample_dt_ms
        );

        transmit_line(
            buffer,
            sizeof(buffer),
            length
        );
    }
}


void Telemetry_SendTurn(
    float yaw_deg,
    float target_deg,
    float yaw_rate_dps,
    float error_deg,
    float effort,
    int left_pwm,
    int right_pwm,
    uint8_t phase,
    uint8_t turn_active
)
{
    uint32_t command_id;
    uint32_t primask;
    char buffer[160];
    int length;

    if (telemetry_uart == NULL || !turn_active)
    {
        return;
    }

    primask = __get_PRIMASK();
    __disable_irq();
    command_id = current_command_id;
    if (primask == 0U)
    {
        __enable_irq();
    }

    length = snprintf(
        buffer,
        sizeof(buffer),
        "TRN,%lu,%lu,%ld,%ld,%ld,%ld,%d,%d,%d,%u\r\n",
        (unsigned long)HAL_GetTick(),
        (unsigned long)command_id,
        (long)scale_by_1000(yaw_deg),
        (long)scale_by_1000(target_deg),
        (long)scale_by_1000(yaw_rate_dps),
        (long)scale_by_1000(error_deg),
        (int)(effort + 0.5f),
        left_pwm,
        right_pwm,
        (unsigned int)phase
    );
    transmit_line(buffer, sizeof(buffer), length);
}


void Telemetry_SendStraight(
    float yaw_deg,
    float target_deg,
    float yaw_rate_dps,
    float error_deg,

    float steer_p_percent,
    float steer_i_percent,
    float steer_d_percent,
    float steer_correction_percent,

    int servo_ccr,
    int servo_center_ccr,
    float steer_percent,

    int left_pwm,
    int right_pwm,

    uint8_t straight_active
)
{
    uint32_t command_id;
    uint32_t primask;

    char buffer[208];
    int length;

    if (telemetry_uart == NULL ||
        !straight_active)
    {
        return;
    }

    primask = __get_PRIMASK();
    __disable_irq();

    command_id = current_command_id;

    if (primask == 0U)
    {
        __enable_irq();
    }

    length = snprintf(
        buffer,
        sizeof(buffer),

        "STR,%lu,%lu,"
        "%ld,%ld,%ld,%ld,"
        "%ld,%ld,%ld,%ld,"
        "%d,%d,%ld,%d,%d\r\n",

        (unsigned long)HAL_GetTick(),
        (unsigned long)command_id,

        (long)scale_by_1000(yaw_deg),
        (long)scale_by_1000(target_deg),
        (long)scale_by_1000(yaw_rate_dps),
        (long)scale_by_1000(error_deg),
        (long)scale_by_1000(steer_p_percent),
        (long)scale_by_1000(steer_i_percent),
        (long)scale_by_1000(steer_d_percent),
        (long)scale_by_1000(steer_correction_percent),

        servo_ccr,
        servo_center_ccr,

        (long)scale_by_1000(steer_percent),

        left_pwm,
        right_pwm
    );

    transmit_line(
        buffer,
        sizeof(buffer),
        length
    );
}
