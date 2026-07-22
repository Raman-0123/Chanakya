"use client";

import { RoomPage } from "@/components/shell/RoomPage";
import { ExecutionRoom } from "@/components/execution/ExecutionRoom";
import { ROOMS } from "@/config/navigation";

const room = ROOMS.find((r) => r.id === "execution")!;

export default function Page() {
  return (
    <RoomPage room={room}>
      <ExecutionRoom />
    </RoomPage>
  );
}
