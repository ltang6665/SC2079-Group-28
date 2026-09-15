import csv
import sys
import os
from collections import defaultdict

import matplotlib.pyplot as plt


SAMPLE_PERIOD = 0.020


def load_log(filename):

    data = defaultdict(
        lambda: {
            'time': [],
            'a': [],
            'b': [],
            'command': ''
        }
    )


    with open(
        filename,
        'r',
        newline=''
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:

            command_id = int(
                row['Command_ID']
            )

            data[command_id]['time'].append(
                float(row['STM_Time_s'])
            )

            data[command_id]['a'].append(
                int(row['Motor_A'])
            )

            data[command_id]['b'].append(
                int(row['Motor_B'])
            )

            data[command_id]['command'] = (
                row['Command']
            )


    return data


def plot_command(
    command_id,
    command_data
):

    times = command_data['time']
    a_vals = command_data['a']
    b_vals = command_data['b']

    command = command_data['command']


    if len(times) < 2:
        return


    # ==========================================
    # Convert global STM32 time to command time
    # ==========================================

    t0 = times[0]

    relative_time = [
        t - t0
        for t in times
    ]


    # ==========================================
    # Calculate acceleration
    # ==========================================

    a_accel = [0.0]

    b_accel = [0.0]

    for i in range(1, len(a_vals)):

        a_speed_change = (
            a_vals[i] - a_vals[i - 1]
        )

        b_speed_change = (
            b_vals[i] - b_vals[i - 1]
        )

        a_accel.append(
            a_speed_change
            / SAMPLE_PERIOD
        )

        b_accel.append(
            b_speed_change
            / SAMPLE_PERIOD
        )


    # ==========================================
    # SPEED GRAPH
    # ==========================================

    plt.figure(
        figsize=(10, 5)
    )

    plt.plot(
        relative_time,
        a_vals,
        label='Motor A (Left)',
        linewidth=2
    )

    plt.plot(
        relative_time,
        b_vals,
        label='Motor B (Right)',
        linewidth=2
    )

    plt.title(
        f'Command {command_id}: {command}'
        '\nWheel Speed'
    )

    plt.xlabel(
        'Time since command start (s)'
    )

    plt.ylabel(
        'Encoder counts / 20 ms'
    )

    plt.legend()

    plt.grid(True)

    plt.tight_layout()

    plt.show()


    # ==========================================
    # ACCELERATION GRAPH
    # ==========================================

    plt.figure(
        figsize=(10, 5)
    )

    plt.plot(
        relative_time,
        a_accel,
        label='Motor A acceleration',
        linewidth=2
    )

    plt.plot(
        relative_time,
        b_accel,
        label='Motor B acceleration',
        linewidth=2
    )

    plt.title(
        f'Command {command_id}: {command}'
        '\nWheel Acceleration'
    )

    plt.xlabel(
        'Time since command start (s)'
    )

    plt.ylabel(
        'Change in encoder speed / s'
    )

    plt.legend()

    plt.grid(True)

    plt.tight_layout()

    plt.show()


def main():

    if len(sys.argv) != 2:

        print(
            "Usage:"
        )

        print(
            "python3 plot_robot_log.py "
            "robot_log.csv"
        )

        return


    filename = sys.argv[1]


    if not os.path.exists(filename):

        print(
            f"File not found: {filename}"
        )

        return


    data = load_log(filename)


    print(
        f"Found {len(data)} command IDs."
    )


    for command_id in sorted(data):

        command = data[
            command_id
        ]['command']

        print(
            f"Plotting command "
            f"{command_id}: {command}"
        )

        plot_command(
            command_id,
            data[command_id]
        )


if __name__ == '__main__':
    main()