// Opt-in at build time; real mode keeps the existing service architecture.
export const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "1"
