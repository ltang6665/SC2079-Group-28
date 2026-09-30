import sys
import matplotlib.pyplot as plt
import pandas as pd


def plot_pi_telemetry(csv_filename):
  try:
    df = pd.read_csv(csv_filename)
  except Exception as e:
    print(f"Error loading CSV file '{csv_filename}': {e}")
    return

  if 'record_type' not in df.columns:
    print(f"Error: 'record_type' column missing in {csv_filename}.")
    return

  # Filter for Wheel PI diagnostic records
  wpi_all = df[df['record_type'] == 'WPI'].copy()
  if wpi_all.empty:
    print(f"No 'WPI' records found in {csv_filename}.")
    return

  # Map command strings from CMD records (if present)
  cmd_map = {}
  if 'CMD' in df['record_type'].values:
    cmd_df = df[df['record_type'] == 'CMD']
    for _, row in cmd_df.iterrows():
      cmd_map[(row['session_id'], row['command_id'])] = row['command']

  # Group by session_id and command_id to isolate individual moves
  grouped = wpi_all.groupby(['session_id', 'command_id'])

  for (session_id, command_id), group in grouped:
    cmd_str = cmd_map.get((session_id, command_id), 'UNKNOWN')

    # 1. Use control_tick_ms if available for precise controller timing
    tick_col = (
        'control_tick_ms'
        if ('control_tick_ms' in group.columns
            and group['control_tick_ms'].notna().any())
        else 'stm_tick_ms'
    )

    group = group.sort_values(by=tick_col)
    time_s = (group[tick_col] - group[tick_col].min()) / 1000.0

    # Create a 4-panel diagnostic figure per command execution
    fig, axes = plt.subplots(4, 1, figsize=(11, 10), sharex=True)
    title_str = (
        f'Wheel PI Diagnostics — {csv_filename} | Session {session_id},'
        f' Command {command_id} [{cmd_str}]'
    )

    # Panel 1: Filtered Wheel Speeds (cps_a_f vs cps_b_f)
    axes[0].plot(
        time_s,
        group['cps_a_f'],
        label='Left Wheel (cps_a_f)',
        color='tab:blue',
    )
    axes[0].plot(
        time_s,
        group['cps_b_f'],
        label='Right Wheel (cps_b_f)',
        color='tab:orange',
    )
    axes[0].set_ylabel('Speed (cps)')
    axes[0].set_title(title_str)
    axes[0].grid(True)
    axes[0].legend(loc='upper right')

    # Panel 2: Wheel Speed Difference Error (wheel_speed_error_cps)
    axes[1].plot(
        time_s,
        group['wheel_speed_error_cps'],
        label='Speed Error (cps)',
        color='tab:red',
    )
    axes[1].axhline(0, color='black', linestyle='--', alpha=0.6)
    axes[1].set_ylabel('Error (cps)')
    axes[1].grid(True)
    axes[1].legend(loc='upper right')

    # Panel 3: Integrator Usage & Dynamic Limits Read from CSV
    if 'wheel_pi_i_limit' in group.columns and group[
        'wheel_pi_i_limit'
    ].notna().any():
      limit = group['wheel_pi_i_limit']
      axes[2].plot(
          time_s,
          limit,
          color='gray',
          linestyle=':',
          label='+Clamp (from CSV)',
      )
      axes[2].plot(
          time_s, -limit, color='gray', linestyle=':', label='-Clamp (from CSV)'
      )
    else:
      # Fallback clamp display if missing in legacy logs
      axes[2].axhline(40000, color='gray', linestyle=':', label='+Clamp (40k)')
      axes[2].axhline(-40000, color='gray', linestyle=':', label='-Clamp (-40k)')

    axes[2].plot(
        time_s,
        group['wheel_pi_i_acc'],
        label='Integrator (wheel_pi_i_acc)',
        color='tab:purple',
    )
    axes[2].set_ylabel('i_acc')
    axes[2].grid(True)
    axes[2].legend(loc='upper right')

    # Panel 4: Applied Controller Output (wheel_pi_off) & Drive Level / PWM
    ax4_off = axes[3]
    line_off = ax4_off.plot(
        time_s,
        group['wheel_pi_off'],
        label='Applied Offset (wheel_pi_off)',
        color='tab:green',
        linewidth=1.5,
    )
    ax4_off.set_ylabel('Offset (compare counts)', color='tab:green')
    ax4_off.tick_params(axis='y', labelcolor='tab:green')
    ax4_off.grid(True)

    # Secondary Y-Axis for Drive Percent
    ax4_drv = ax4_off.twinx()
    line_drv = ax4_drv.plot(
        time_s,
        group['drive_percent'],
        label='Drive Level (%)',
        color='tab:gray',
        linestyle='--',
        alpha=0.7,
    )
    ax4_drv.set_ylabel('Drive %', color='tab:gray')
    ax4_drv.tick_params(axis='y', labelcolor='tab:gray')

    # Combine legends for dual y-axis in Panel 4
    lines = line_off + line_drv
    labels = [l.get_label() for l in lines]
    ax4_off.legend(lines, labels, loc='upper right')

    axes[3].set_xlabel('Time (seconds)')

    plt.tight_layout()

  print('Displaying plot window...')
  plt.show()


if __name__ == '__main__':
  if len(sys.argv) < 2:
    print('Usage: python pid_plotter.py <path_to_csv_file>')
  else:
    plot_pi_telemetry(sys.argv[1])