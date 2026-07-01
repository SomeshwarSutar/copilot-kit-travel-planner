/// <reference types="vite/client" />

// Allow importing CSS files
declare module "*.css" {
  const content: Record<string, string>;
  export default content;
}
