/// <reference types="vite/client" />
// import.meta.glob types for the contract mock, which lives outside src/ and node_modules' reach.
export {
  examples,
  handlers,
} from "../../../docs/contracts/brands-api/mock/handlers";
export type { Example } from "../../../docs/contracts/brands-api/mock/handlers";
