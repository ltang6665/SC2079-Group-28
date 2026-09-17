/*
 * telementary.h
 *
 *  Created on: 15 Sept 2026
 *      Author: luther tang
 */

#ifndef INC_TELEMETRY_H_
#define INC_TELEMETRY_H_

#include "main.h"
#include <stdint.h>

/*
 * Initialise the telemetry module.
 *
 * uart should be the UART connected to the Raspberry Pi GPIO UART.
 * In our setup this will be &huart1.
 */
void Telemetry_Init(UART_HandleTypeDef *uart);

/*
 * Called whenever a new robot command actually begins executing.
 *
 * IMPORTANT:
 * This function does NOT transmit over UART.
 * It only records the event so it is safe to call from the existing
 * command-start path, which can currently be reached from the UART ISR.
 */
void Telemetry_StartCommand(const char *command_name, int value);

/*
 * Send one encoder sample.
 *
 * motor_a and motor_b are the encoder deltas measured over the 20 ms window.
 *
 * command_active:
 *   1 -> associate sample with current command
 *   0 -> mark sample as idle using command ID 0
 */
void Telemetry_SendEncoder(
    int16_t motor_a,
    int16_t motor_b,
    uint8_t command_active
);

#endif /* INC_TELEMETRY_H_ */
