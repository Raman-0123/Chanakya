import {
  Radar,
  Globe2,
  Users,
  Brain,
  FlaskConical,
  Rocket,
  type LucideIcon,
} from "lucide-react";

export interface NavRoom {
  id: string;
  label: string;
  short: string;
  href: string;
  room: number;
  icon: LucideIcon;
  description: string;
}

/** The six operational rooms — the platform's primary navigation. */
export const ROOMS: NavRoom[] = [
  {
    id: "intelligence",
    label: "Global Intelligence",
    short: "Intel",
    href: "/intelligence",
    room: 1,
    icon: Radar,
    description: "Monitor the world — events, shipping, prices, sanctions.",
  },
  {
    id: "digital-twin",
    label: "Digital Twin",
    short: "Twin",
    href: "/digital-twin",
    room: 2,
    icon: Globe2,
    description: "India's energy supply chain as a living geospatial system.",
  },
  {
    id: "council",
    label: "Agent Council",
    short: "Council",
    href: "/council",
    room: 3,
    icon: Users,
    description: "Six specialized AI advisors reason, cite evidence, and disagree.",
  },
  {
    id: "decision",
    label: "Decision Center",
    short: "Decide",
    href: "/decision",
    room: 4,
    icon: Brain,
    description: "Reconcile agent outputs into ranked national response strategies.",
  },
  {
    id: "simulation",
    label: "Scenario Lab",
    short: "Simulate",
    href: "/simulation",
    room: 5,
    icon: FlaskConical,
    description: "Model disruption futures before acting.",
  },
  {
    id: "execution",
    label: "Mission Execution",
    short: "Execute",
    href: "/execution",
    room: 6,
    icon: Rocket,
    description: "Turn an approved strategy into an executable operational playbook.",
  },
];

/** The operating loop CHANAKYA runs, shown in the shell. */
export const OPERATING_LOOP = [
  "Observe",
  "Understand",
  "Predict",
  "Simulate",
  "Decide",
  "Execute",
] as const;
