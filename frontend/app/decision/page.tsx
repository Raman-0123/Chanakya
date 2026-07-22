import { ROOMS } from "@/config/navigation";
import { RoomScaffold } from "@/components/shell/RoomScaffold";
import { DecisionRoom } from "@/components/decision/DecisionRoom";

const room = ROOMS.find((r) => r.id === "decision")!;

export default function DecisionPage() {
  return (
    <RoomScaffold room={room}>
      <DecisionRoom />
    </RoomScaffold>
  );
}
