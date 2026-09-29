#include "telemetry.h"

#include <stdio.h>
#include <string.h>

#define TELEMETRY_COMMAND_NAME_LEN 16
#define TELEMETRY_FAULT_CODE_LEN   20

static UART_HandleTypeDef *telemetry_uart = NULL;

static volatile uint32_t current_command_id = 0;
static volatile uint8_t command_pending = 0;
static char pending_command_name[TELEMETRY_COMMAND_NAME_LEN];
static volatile int pending_command_value = 0;
static volatile uint32_t pending_command_tick = 0;

static volatile uint8_t fault_pending = 0;
static volatile uint32_t pending_fault_tick = 0;
static char pending_fault_code[TELEMETRY_FAULT_CODE_LEN];


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
        10
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
    uint32_t command_tick = 0U;
    uint32_t fault_tick = 0U;
    int command_value = 0;
    char command_name[TELEMETRY_COMMAND_NAME_LEN] = {0};
    char fault_code[TELEMETRY_FAULT_CODE_LEN] = {0};
    uint32_t primask;

    if (telemetry_uart == NULL)
    {
        return;
    }

    primask = __get_PRIMASK();
    __disable_irq();

    command_id = current_command_id;

    if (command_pending)
    {
        send_command = 1U;
        command_tick = pending_command_tick;
        command_value = pending_command_value;
        memcpy(command_name, pending_command_name, sizeof(command_name));
        command_pending = 0U;
    }

    if (fault_pending)
    {
        send_fault = 1U;
        fault_tick = pending_fault_tick;
        memcpy(fault_code, pending_fault_code, sizeof(fault_code));
        fault_pending = 0U;
    }

    if (primask == 0U)
    {
        __enable_irq();
    }

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
        transmit_line(buffer, sizeof(buffer), length);
    }

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
        transmit_line(buffer, sizeof(buffer), length);
    }

    {
        uint32_t sample_command_id = command_active ? command_id : 0U;
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
        transmit_line(buffer, sizeof(buffer), length);
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
    char buffer[144];
    int length;

    if (telemetry_uart == NULL || !straight_active)
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
        "STR,%lu,%lu,%ld,%ld,%ld,%ld,%d,%d,%ld,%d,%d\r\n",
        (unsigned long)HAL_GetTick(),
        (unsigned long)command_id,
        (long)scale_by_1000(yaw_deg),
        (long)scale_by_1000(target_deg),
        (long)scale_by_1000(yaw_rate_dps),
        (long)scale_by_1000(error_deg),
        servo_ccr,
        servo_center_ccr,
        (long)scale_by_1000(steer_percent),
        left_pwm,
        right_pwm
    );
    transmit_line(buffer, sizeof(buffer), length);
}
