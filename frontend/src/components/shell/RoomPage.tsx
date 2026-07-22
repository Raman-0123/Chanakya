import type { ReactNode } from "react";
import type { NavRoom } from "@/config/navigation";
import { RoomScaffold } from "./RoomScaffold";

/**
 * Page wrapper for a single operational room. Offsets content past the global
 * chrome (h-12 StatusBar on top, w-14 NavRail on the left) so nothing is hidden,
 * then frames it with the room header. Pass `bare` for full-bleed rooms (the map).
 */
export function RoomPage({
  room,
  children,
  bare = false,
}: {
  room: NavRoom;
  children: ReactNode;
  bare?: boolean;
}) {
  return (
    <div className="h-full pt-12 pl-14">
      {bare ? children : <RoomScaffold room={room}>{children}</RoomScaffold>}
    </div>
  );
}
