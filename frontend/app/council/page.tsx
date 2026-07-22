"use client";

import { RoomPage } from "@/components/shell/RoomPage";
import { CouncilRoom } from "@/components/council/CouncilRoom";
import { ROOMS } from "@/config/navigation";

const room = ROOMS.find((r) => r.id === "council")!;

export default function Page() {
  return (
    <RoomPage room={room}>
      <CouncilRoom />
    </RoomPage>
  );
}
