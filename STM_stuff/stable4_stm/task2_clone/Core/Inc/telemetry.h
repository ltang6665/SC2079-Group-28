#ifndef INC_TELEMETRY_H_
#define INC_TELEMETRY_H_

#include "main.h"
#include <stdint.h>

void Telemetry_Init(UART_HandleTypeDef *uart);
void Telemetry_StartCommand(const char *command_name, int value);

/* Records a fault for EncoderTask to transmit; safe to call from another task. */
void Telemetry_RecordFault(const char *fault_code);

/* Called by EncoderTask. sample_dt_ms is the real encoder measurement window. */
void Telemetry_SendEncoder(
    int16_t motor_a,
    int16_t motor_b,
    uint8_t command_active,
    uint16_t sample_dt_ms
);

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
);

/* Optional straight-run record used to diagnose veering and servo correction. */
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
);

#endif /* INC_TELEMETRY_H_ */
