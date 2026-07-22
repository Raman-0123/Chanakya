import { ROOMS } from "@/config/navigation";
import { RoomScaffold } from "@/components/shell/RoomScaffold";
import { DigitalTwinRoom } from "@/components/twin/DigitalTwinRoom";

const room = ROOMS.find((r) => r.id === "digital-twin")!;

export default function DigitalTwinPage() {
  return (
    <RoomScaffold room={room}>
      <DigitalTwinRoom />
    </RoomScaffold>
  );
}
