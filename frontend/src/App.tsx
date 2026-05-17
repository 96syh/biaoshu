import { AppView } from './features/app/AppView';
import { useBidWorkspaceController } from './features/app/useBidWorkspaceController';
import { WorkspaceProvider } from './app/WorkspaceProvider';

const App = () => {
  const controller = useBidWorkspaceController();
  return (
    <WorkspaceProvider controller={controller}>
      <AppView />
    </WorkspaceProvider>
  );
};

export default App;
