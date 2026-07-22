"use client";

import { RoomPage } from "@/components/shell/RoomPage";
import { IntelligenceRoom } from "@/components/intelligence/IntelligenceRoom";
import { ROOMS } from "@/config/navigation";

const room = ROOMS.find((r) => r.id === "intelligence")!;

export default function Page() {
  return (
    <RoomPage room={room}>
      <IntelligenceRoom />
    </RoomPage>
  );
}
