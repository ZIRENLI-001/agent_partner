import { request } from "./client";

export interface PlatformContext {
  user: {
    user_id: string;
    display_name: string;
  };
  workspace: {
    workspace_id: string;
    name: string;
  };
  project: {
    project_id: string;
    name: string;
  };
}

export function getPlatformContext() {
  return request<PlatformContext>("/api/context");
}
