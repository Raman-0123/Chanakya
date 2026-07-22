import { ROOMS } from "@/config/navigation";
import { RoomScaffold } from "@/components/shell/RoomScaffold";
import { ExecutionRoom } from "@/components/execution/ExecutionRoom";

const room = ROOMS.find((r) => r.id === "execution")!;

export default function ExecutionPage() {
  return (
    <RoomScaffold room={room}>
      <ExecutionRoom />
    </RoomScaffold>
  );
}
