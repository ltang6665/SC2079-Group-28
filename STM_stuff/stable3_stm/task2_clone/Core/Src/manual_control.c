#include "manual_control.h"
#include <stddef.h>
#include <string.h>

static const ManualSetpoint stopped = {0, 0, 0, 0};

static int sign_of(int value)
{
    return (value > 0) - (value < 0);
}

/* Bounded integer parsing: do not let sscanf/atoi overflow on damaged input. */
static void skip_space(const char **cursor)
{
    while (**cursor == ' ' || **cursor == '\t') ++*cursor;
}

static bool read_number(const char **cursor, uint32_t maximum, uint32_t *result)
{
    const char *p = *cursor;
    uint32_t value = 0U;
    skip_space(&p);
    if (*p < '0' || *p > '9') return false;
    do {
        uint32_t digit = (uint32_t)(*p - '0');
        if (digit > maximum || value > (maximum - digit) / 10U) return false;
        value = value * 10U + digit;
        ++p;
    } while (*p >= '0' && *p <= '9');
    if (*p != '\0' && *p != ' ' && *p != '\t') return false;
    *cursor = p;
    *result = value;
    return true;
}

static bool read_signed(const char **cursor, int maximum, int *result)
{
    uint32_t magnitude;
    int polarity = 1;
    skip_space(cursor);
    if (**cursor == '-') { polarity = -1; ++*cursor; }
    /* Reject an empty sign or a sign separated from its number. */
    if (**cursor < '0' || **cursor > '9') return false;
    if (!read_number(cursor, (uint32_t)maximum, &magnitude)) return false;
    *result = polarity * (int)magnitude;
    return true;
}

static bool valid_setpoint(ManualSetpoint s)
{
    if (s.direction < -1 || s.direction > 1 || s.steering < -100 || s.steering > 100 ||
        s.left_effort < 0 || s.left_effort > MANUAL_MAX_EFFORT ||
        s.right_effort < 0 || s.right_effort > MANUAL_MAX_EFFORT) return false;
    if (s.direction == 0)
        return s.steering == 0 && s.left_effort == 0 && s.right_effort == 0;
    return s.left_effort > 0 || s.right_effort > 0;
}

bool Manual_ParseLine(const char *line, ManualMessage *message)
{
    ManualMessage parsed = {0};
    const char *p;
    uint32_t left, right;
    if (line == NULL || message == NULL) return false;
    if (strncmp(line, "jbegin ", 7U) == 0) {
        p = line + 7;
        parsed.type = MANUAL_BEGIN;
        if (!read_number(&p, UINT32_MAX, &parsed.session) || parsed.session == 0U) return false;
    } else if (strncmp(line, "j ", 2U) == 0) {
        p = line + 2;
        parsed.type = MANUAL_FRAME;
        if (!read_number(&p, UINT32_MAX, &parsed.session) || parsed.session == 0U ||
            !read_number(&p, UINT32_MAX, &parsed.sequence) || parsed.sequence == 0U ||
            !read_signed(&p, 1, &parsed.setpoint.direction) ||
            !read_signed(&p, 100, &parsed.setpoint.steering) ||
            !read_number(&p, MANUAL_MAX_EFFORT, &left) ||
            !read_number(&p, MANUAL_MAX_EFFORT, &right)) return false;
        parsed.setpoint.left_effort = (int)left;
        parsed.setpoint.right_effort = (int)right;
        if (!valid_setpoint(parsed.setpoint)) return false;
    } else {
        return false;
    }
    skip_space(&p);
    if (*p != '\0') return false;
    *message = parsed;
    return true;
}

void Manual_Init(ManualControl *control)
{
    memset(control, 0, sizeof(*control));
}

void Manual_Begin(ManualControl *control, uint32_t session, uint32_t now_ms)
{
    Manual_Init(control);
    control->owns_motors = true;
    control->session = session;
    control->last_update_ms = now_ms;
    control->drive_after_ms = now_ms;
}

bool Manual_Tick(ManualControl *control, uint32_t now_ms)
{
    if (control->owns_motors && !control->locked &&
        (uint32_t)(now_ms - control->last_update_ms) >= MANUAL_WATCHDOG_MS) {
        control->locked = true;
        control->requested = stopped;
        return true;
    }
    return false;
}

bool Manual_Accept(ManualControl *control, const ManualMessage *message, uint32_t now_ms)
{
    uint32_t advance;
    /* Check expiry BEFORE a late frame can refresh the timestamp. */
    (void)Manual_Tick(control, now_ms);
    if (!control->owns_motors || control->locked || message->type != MANUAL_FRAME ||
        message->session != control->session || message->sequence == 0U ||
        !valid_setpoint(message->setpoint)) return false;
    advance = message->sequence - control->last_sequence;
    if (control->have_sequence && (advance == 0U || advance >= 0x80000000U)) return false;
    if (!control->neutral_seen && message->setpoint.direction != 0) return false;

    if (message->setpoint.direction != 0 &&
        (message->setpoint.direction != control->requested.direction ||
         sign_of(message->setpoint.steering) != sign_of(control->requested.steering)))
        control->drive_after_ms = now_ms + MANUAL_TRANSITION_MS;

    control->requested = message->setpoint;
    control->last_sequence = message->sequence;
    control->have_sequence = true;
    control->neutral_seen = true;
    control->last_update_ms = now_ms;
    return true;
}

ManualSetpoint Manual_Output(const ManualControl *control, uint32_t now_ms)
{
    ManualSetpoint output;
    if (!control->owns_motors || control->locked ||
        (uint32_t)(now_ms - control->last_update_ms) >= MANUAL_WATCHDOG_MS) return stopped;
    output = control->requested;
    if (output.direction != 0 && (int32_t)(now_ms - control->drive_after_ms) < 0) {
        output.direction = 0;
        output.left_effort = 0;
        output.right_effort = 0;
        /* Keep requested steering while the wheels brake and the servo settles. */
    }
    return output;
}
