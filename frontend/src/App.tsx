import { AppView } from './features/app/AppView';
import { useBidWorkspaceController } from './features/app/useBidWorkspaceController';

const App = () => <AppView controller={useBidWorkspaceController()} />;

export default App;
