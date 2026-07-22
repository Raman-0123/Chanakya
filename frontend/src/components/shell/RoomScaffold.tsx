import type { ReactNode } from "react";
import type { NavRoom } from "@/config/navigation";

interface RoomScaffoldProps {
  room: NavRoom;
  children?: ReactNode;
}

/** Consistent header + working area for each operational room. */
export function RoomScaffold({ room, children }: RoomScaffoldProps) {
  const Icon = room.icon;
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-line px-6 py-4">
        <div className="grid h-9 w-9 place-items-center rounded-md border border-line-strong bg-panel-raised text-signal">
          <Icon size={18} strokeWidth={1.75} />
        </div>
        <div>
          <div className="label-terminal">Room {room.room}</div>
          <h1 className="text-base font-semibold text-ink">{room.label}</h1>
        </div>
        <p className="ml-4 hidden max-w-xl text-sm text-ink-muted lg:block">
          {room.description}
        </p>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden">{children}</div>
    </div>
  );
}

/** Temporary body used before a room is fully implemented. */
export function RoomComingSoon({ room }: { room: NavRoom }) {
  return (
    <div className="grid h-full place-items-center blueprint">
      <div className="text-center">
        <div className="label-terminal">Module initializing</div>
        <p className="mt-2 max-w-md text-sm text-ink-muted">{room.description}</p>
      </div>
    </div>
  );
}
