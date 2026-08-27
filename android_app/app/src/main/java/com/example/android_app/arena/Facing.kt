package com.example.android_app.arena

/** Compass direction (also used for target-face annotation). */
enum class Facing(val code: String) {
    NORTH("N"),
    EAST("E"),
    SOUTH("S"),
    WEST("W");

    fun turnLeft(): Facing = values()[(ordinal + 3) % 4]
    fun turnRight(): Facing = values()[(ordinal + 1) % 4]

    companion object {
        fun fromCode(s: String?): Facing? = when (s?.trim()?.uppercase()) {
            "N", "NORTH" -> NORTH
            "E", "EAST"  -> EAST
            "S", "SOUTH" -> SOUTH
            "W", "WEST"  -> WEST
            else -> null
        }
    }
}
