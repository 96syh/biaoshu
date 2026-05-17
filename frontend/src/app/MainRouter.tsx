import { canEnterRoute } from './routeGuards';
import { fallbackRoute, WorkspaceRouteKey, workspaceRoutes } from './routes';
import { useWorkspace } from './WorkspaceProvider';

const isWorkspaceRouteKey = (value: string): value is WorkspaceRouteKey => (
  workspaceRoutes.some(route => route.key === value)
);

export const MainRouter = () => {
  const controller = useWorkspace();
  const routeKey = isWorkspaceRouteKey(controller.currentPage)
    ? controller.currentPage
    : fallbackRoute.key;
  const route = workspaceRoutes.find(item => item.key === routeKey) || fallbackRoute;
  const access = canEnterRoute(route, controller);
  const Page = route.page;

  if (!access.enabled) {
    return (
      <div className="page-card">
        <div className="empty-state">
          <strong>{route.label}暂不可用</strong>
          <span>{access.reason}</span>
          <button type="button" className="text-link" onClick={() => controller.goToPage('project')}>
            返回上传文件
          </button>
        </div>
      </div>
    );
  }

  return <Page controller={controller} />;
};
