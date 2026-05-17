import React, { createContext, useContext } from 'react';
import type { BidWorkspaceController } from '../features/app/useBidWorkspaceController';

const WorkspaceContext = createContext<BidWorkspaceController | null>(null);

type WorkspaceProviderProps = {
  controller: BidWorkspaceController;
  children: React.ReactNode;
};

export const WorkspaceProvider = ({ controller, children }: WorkspaceProviderProps) => (
  <WorkspaceContext.Provider value={controller}>
    {children}
  </WorkspaceContext.Provider>
);

export const useWorkspace = () => {
  const controller = useContext(WorkspaceContext);
  if (!controller) {
    throw new Error('useWorkspace must be used inside WorkspaceProvider');
  }
  return controller;
};
