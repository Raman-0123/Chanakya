"use client";

import { RoomPage } from "@/components/shell/RoomPage";
import { DecisionRoom } from "@/components/decision/DecisionRoom";
import { ROOMS } from "@/config/navigation";

const room = ROOMS.find((r) => r.id === "decision")!;

export default function Page() {
  return (
    <RoomPage room={room}>
      <DecisionRoom />
    </RoomPage>
  );
}
