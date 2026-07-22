"use client";

import { RoomPage } from "@/components/shell/RoomPage";
import { DigitalTwinRoom } from "@/components/twin/DigitalTwinRoom";
import { ROOMS } from "@/config/navigation";

const room = ROOMS.find((r) => r.id === "digital-twin")!;

export default function Page() {
  return (
    <RoomPage room={room} bare>
      <DigitalTwinRoom />
    </RoomPage>
  );
}
