package com.example.android_app.bluetooth

import com.example.android_app.arena.Facing
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ProtocolTest {

    // ── Outbound (C.3, C.6, C.7) ──

    @Test fun `obstacle line uses OBSTACLE prefix and 3 fields`() {
        assertEquals("OBSTACLE,7,4,12", Protocol.obstacle(7, 4, 12))
    }

    @Test fun `obstacle deletion carries only the id`() {
        assertEquals("OBSTACLE_DEL,3", Protocol.obstacleDeleted(3))
    }

    @Test fun `face line uses compass code`() {
        assertEquals("FACE,2,E", Protocol.face(2, Facing.EAST))
        assertEquals("FACE,5,N", Protocol.face(5, Facing.NORTH))
    }

    @Test fun `move commands use single character tokens`() {
        assertEquals("ROBOT_MOVE,F", Protocol.move(Protocol.MoveCmd.FORWARD))
        assertEquals("ROBOT_MOVE,B", Protocol.move(Protocol.MoveCmd.BACKWARD))
        assertEquals("ROBOT_MOVE,L", Protocol.move(Protocol.MoveCmd.LEFT))
        assertEquals("ROBOT_MOVE,R", Protocol.move(Protocol.MoveCmd.RIGHT))
        assertEquals("ROBOT_MOVE,S", Protocol.move(Protocol.MoveCmd.STOP))
    }

    // ── Inbound (C.9, C.10) — exact wire format from the checklist ──

    @Test fun `TARGET line parses obstacle and target ids`() {
        val msg = Protocol.parse("TARGET,4,11") as Protocol.Inbound.Target
        assertEquals(4, msg.obstacleId)
        assertEquals(11, msg.targetId)
    }

    @Test fun `TARGET line tolerates whitespace`() {
        val msg = Protocol.parse("TARGET, 4 , 11 ") as Protocol.Inbound.Target
        assertEquals(4, msg.obstacleId)
        assertEquals(11, msg.targetId)
    }

    @Test fun `ROBOT line parses coordinates and direction`() {
        val msg = Protocol.parse("ROBOT,10,15,E") as Protocol.Inbound.Robot
        assertEquals(10, msg.x)
        assertEquals(15, msg.y)
        assertEquals(Facing.EAST, msg.facing)
    }

    @Test fun `ROBOT line accepts full direction name`() {
        val msg = Protocol.parse("ROBOT,0,0,NORTH") as Protocol.Inbound.Robot
        assertEquals(Facing.NORTH, msg.facing)
    }

    @Test fun `unknown lines fall through to Unknown`() {
        val msg = Protocol.parse("HELLO WORLD")
        assertTrue(msg is Protocol.Inbound.Unknown)
    }

    @Test fun `TARGET with non-numeric fields is Unknown`() {
        val msg = Protocol.parse("TARGET,foo,bar")
        assertTrue(msg is Protocol.Inbound.Unknown)
    }

    @Test fun `ROBOT with bad direction is Unknown`() {
        val msg = Protocol.parse("ROBOT,1,2,Z")
        assertTrue(msg is Protocol.Inbound.Unknown)
    }
}
