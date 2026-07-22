import { ROOMS } from "@/config/navigation";
import { RoomScaffold } from "@/components/shell/RoomScaffold";
import { CouncilRoom } from "@/components/council/CouncilRoom";

const room = ROOMS.find((r) => r.id === "council")!;

export default function CouncilPage() {
  return (
    <RoomScaffold room={room}>
      <CouncilRoom />
    </RoomScaffold>
  );
}
