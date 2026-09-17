/*
 * telementry.c
 *
 *  Created on: 15 Sept 2026
 *      Author: luther tang
 */
#include "telemetry.h"

#include <stdio.h>
#include <string.h>

#define TELEMETRY_COMMAND_NAME_LEN 16

/*
 * UART used exclusively for telemetry.
 *
 * We store a pointer instead of directly referring to huart1 so that
 * telemetry.c does not depend specifically on USART1.
 */
static UART_HandleTypeDef *telemetry_uart = NULL;


/*
 * Current command information.
 */
static volatile uint32_t current_command_id = 0;

static volatile uint8_t command_pending = 0;

static char pending_command_name[TELEMETRY_COMMAND_NAME_LEN];

static volatile int pending_command_value = 0;

static volatile uint32_t pending_command_tick = 0;


/*
 * Initialise telemetry.
 */
void Telemetry_Init(UART_HandleTypeDef *uart)
{
    telemetry_uart = uart;

    current_command_id = 0;
    command_pending = 0;

    pending_command_name[0] = '\0';
    pending_command_value = 0;
    pending_command_tick = 0;
}


/*
 * Record the start of a new command.
 *
 * No UART transmission happens here.
 *
 * This is intentional because start_next_from_queue() can currently
 * be called from HAL_UART_RxCpltCallback().
 */
void Telemetry_StartCommand(const char *command_name, int value)
{
    if (command_name == NULL)
    {
        return;
    }

    /*
     * Prepare the command name first.
     */
    char temp_name[TELEMETRY_COMMAND_NAME_LEN];

    strncpy(
        temp_name,
        command_name,
        TELEMETRY_COMMAND_NAME_LEN - 1
    );

    temp_name[TELEMETRY_COMMAND_NAME_LEN - 1] = '\0';


    /*
     * Protect shared state from the encoder task.
     *
     * Save PRIMASK so this works whether we arrived here from a task
     * or from an interrupt.
     */
    uint32_t primask = __get_PRIMASK();

    __disable_irq();

    current_command_id++;

    pending_command_tick = HAL_GetTick();
    pending_command_value = value;

    memcpy(
        pending_command_name,
        temp_name,
        TELEMETRY_COMMAND_NAME_LEN
    );

    /*
     * Set this LAST.
     *
     * Once command_pending becomes 1, EncoderTask is allowed to consume
     * the information above.
     */
    command_pending = 1;

    if (primask == 0U)
    {
        __enable_irq();
    }
}


/*
 * Called from EncoderTask every 20 ms.
 *
 * UART transmission happens here, NOT inside the command RX interrupt.
 */
void Telemetry_SendEncoder(
    int16_t motor_a,
    int16_t motor_b,
    uint8_t command_active
)
{
    if (telemetry_uart == NULL)
    {
        return;
    }


    uint32_t command_id;
    uint8_t send_command = 0;

    uint32_t command_tick = 0;
    int command_value = 0;

    char command_name[TELEMETRY_COMMAND_NAME_LEN];


    /*
     * Snapshot the shared telemetry state.
     */
    uint32_t primask = __get_PRIMASK();

    __disable_irq();

    command_id = current_command_id;

    if (command_pending)
    {
        send_command = 1;

        command_tick = pending_command_tick;
        command_value = pending_command_value;

        memcpy(
            command_name,
            pending_command_name,
            TELEMETRY_COMMAND_NAME_LEN
        );

        command_pending = 0;
    }

    if (primask == 0U)
    {
        __enable_irq();
    }


    /*
     * First report a pending command-start event.
     *
     * Format:
     *
     * CMD,<command_id>,<stm32_tick>,<command>:<value>
     *
     * Example:
     *
     * CMD,7,15320,FWD_CM:50
     */
    if (send_command)
    {
        char cmd_buf[64];

        int n = snprintf(
            cmd_buf,
            sizeof(cmd_buf),
            "CMD,%lu,%lu,%s:%d\r\n",
            (unsigned long)command_id,
            (unsigned long)command_tick,
            command_name,
            command_value
        );

        if (n > 0)
        {
            HAL_UART_Transmit(
                telemetry_uart,
                (uint8_t *)cmd_buf,
                (uint16_t)n,
                10
            );
        }
    }


    /*
     * Encoder sample.
     *
     * When the robot is between commands we report command ID 0.
     *
     * Format:
     *
     * ENC,<stm32_tick>,<command_id>,<motor_a>,<motor_b>
     *
     * Example:
     *
     * ENC,15340,7,18,17
     */
    uint32_t sample_command_id;

    if (command_active)
    {
        sample_command_id = command_id;
    }
    else
    {
        sample_command_id = 0;
    }

    char enc_buf[64];

    int n = snprintf(
        enc_buf,
        sizeof(enc_buf),
        "ENC,%lu,%lu,%d,%d\r\n",
        (unsigned long)HAL_GetTick(),
        (unsigned long)sample_command_id,
        (int)motor_a,
        (int)motor_b
    );

    if (n > 0)
    {
        HAL_UART_Transmit(
            telemetry_uart,
            (uint8_t *)enc_buf,
            (uint16_t)n,
            10
        );
    }
}


static int32_t scale_by_1000(float value)
{
    float scaled = value * 1000.0f;

    if (scaled >= 0.0f)
    {
        scaled += 0.5f;
    }
    else
    {
        scaled -= 0.5f;
    }

    return (int32_t)scaled;
}


/*
 * Closed-loop turn sample.
 *
 * Wire format (angles/rate are scaled by 1000):
 *
 * TRN,<tick>,<id>,<yaw_mdeg>,<target_mdeg>,<rate_mdps>,
 *     <error_mdeg>,<effort>,<left_pwm>,<right_pwm>,<phase>
 */
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
    if (telemetry_uart == NULL || !turn_active)
    {
        return;
    }

    uint32_t command_id;
    uint32_t primask = __get_PRIMASK();

    __disable_irq();
    command_id = current_command_id;

    if (primask == 0U)
    {
        __enable_irq();
    }

    char turn_buf[160];

    int n = snprintf(
        turn_buf,
        sizeof(turn_buf),
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

    if (n > 0 && n < (int)sizeof(turn_buf))
    {
        HAL_UART_Transmit(
            telemetry_uart,
            (uint8_t *)turn_buf,
            (uint16_t)n,
            10
        );
    }
}

