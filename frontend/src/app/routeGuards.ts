import type { BidWorkspaceController } from '../features/app/useBidWorkspaceController';
import type { WorkspaceRoute } from './routes';

export interface RouteAccess {
  enabled: boolean;
  reason: string;
}

export const canEnterRoute = (
  route: WorkspaceRoute,
  controller: BidWorkspaceController,
): RouteAccess => controller.workflowAccess(route.key);
