// Radix Toast, themed to Semant plum v1.3, with a tiny imperative API.
// Wrap the app once in <ToastProvider>; call const { toast } = useToast().
import { createContext, useContext, useState, useCallback } from 'react';
import * as RadixToast from '@radix-ui/react-toast';
import { X, CheckCircle2, AlertCircle, Info } from 'lucide-react';
import './Toast.css';

const ToastContext = createContext(null);

// Module-level monotonic id — avoids the Date.now() collision class.
let idSeq = 0;

const ICONS = {
  default: <Info size={17} />,
  success: <CheckCircle2 size={17} />,
  error: <AlertCircle size={17} />,
  info: <Info size={17} />,
};

export function ToastProvider({ children, swipeDirection = 'right' }) {
  const [toasts, setToasts] = useState([]);

  const dismiss = useCallback((id) => {
    setToasts((list) => list.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(({ title, description, variant = 'default', duration = 4500 }) => {
    idSeq += 1;
    const id = idSeq;
    setToasts((list) => [...list, { id, title, description, variant, duration }]);
    return id;
  }, []);

  return (
    <ToastContext.Provider value={{ toast, dismiss }}>
      <RadixToast.Provider swipeDirection={swipeDirection}>
        {children}
        {toasts.map((t) => (
          <RadixToast.Root
            key={t.id}
            className={`ui-toast ui-toast--${t.variant}`}
            duration={t.duration}
            onOpenChange={(open) => { if (!open) dismiss(t.id); }}
          >
            <span className="ui-toast-icon">{ICONS[t.variant] || ICONS.default}</span>
            <div className="ui-toast-text">
              {t.title && <RadixToast.Title className="ui-toast-title">{t.title}</RadixToast.Title>}
              {t.description && (
                <RadixToast.Description className="ui-toast-desc">{t.description}</RadixToast.Description>
              )}
            </div>
            <RadixToast.Close className="ui-toast-close" aria-label="Dismiss">
              <X size={15} />
            </RadixToast.Close>
          </RadixToast.Root>
        ))}
        <RadixToast.Viewport className="ui-toast-viewport" />
      </RadixToast.Provider>
    </ToastContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components -- provider + its hook co-located (matches ThemeContext)
export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within <ToastProvider>');
  return ctx;
}
