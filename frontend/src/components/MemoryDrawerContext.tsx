import {
  createContext,
  useContext,
  useState,
  type ReactNode,
} from 'react';
import { MemoryDrawer } from './MemoryDrawer';

interface MemoryDrawerContextValue {
  openMemory: (memoryId: string) => void;
}

const MemoryDrawerContext = createContext<MemoryDrawerContextValue | null>(null);

export function MemoryDrawerProvider({ children }: { children: ReactNode }) {
  const [memoryId, setMemoryId] = useState<string | null>(null);

  return (
    <MemoryDrawerContext.Provider value={{ openMemory: setMemoryId }}>
      {children}
      <MemoryDrawer
        memoryId={memoryId}
        open={Boolean(memoryId)}
        onClose={() => setMemoryId(null)}
      />
    </MemoryDrawerContext.Provider>
  );
}

export function useMemoryDrawer(): MemoryDrawerContextValue {
  const context = useContext(MemoryDrawerContext);
  if (!context) {
    throw new Error('useMemoryDrawer 必须在 MemoryDrawerProvider 内使用');
  }
  return context;
}
