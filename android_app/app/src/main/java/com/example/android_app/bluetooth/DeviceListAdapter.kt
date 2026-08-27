package com.example.android_app.bluetooth

import android.annotation.SuppressLint
import android.bluetooth.BluetoothDevice
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView
import com.example.android_app.R

class DeviceListAdapter(
    private val onClick: (BluetoothDevice) -> Unit,
) : RecyclerView.Adapter<DeviceListAdapter.VH>() {

    private val items = mutableListOf<BluetoothDevice>()

    @SuppressLint("NotifyDataSetChanged")
    fun submit(newItems: List<BluetoothDevice>) {
        items.clear()
        items.addAll(newItems)
        notifyDataSetChanged()
    }

    fun addIfMissing(device: BluetoothDevice) {
        if (items.none { it.address == device.address }) {
            items.add(device)
            notifyItemInserted(items.size - 1)
        }
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_device, parent, false)
        return VH(view)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        holder.bind(items[position])
    }

    override fun getItemCount(): Int = items.size

    inner class VH(itemView: View) : RecyclerView.ViewHolder(itemView) {
        private val name: TextView = itemView.findViewById(R.id.deviceName)
        private val address: TextView = itemView.findViewById(R.id.deviceAddress)

        @SuppressLint("MissingPermission")
        fun bind(device: BluetoothDevice) {
            name.text = try { device.name ?: "Unknown" } catch (_: SecurityException) { "Unknown" }
            address.text = device.address
            itemView.setOnClickListener { onClick(device) }
        }
    }
}