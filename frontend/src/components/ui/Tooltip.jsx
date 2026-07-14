// Radix Tooltip, themed to Semant plum v1.3.
// Wrap the app once in <TooltipProvider>; use <Tooltip content="…"> per target.
import * as RadixTooltip from '@radix-ui/react-tooltip';
import './Tooltip.css';

export const TooltipProvider = RadixTooltip.Provider;

export function Tooltip({ content, children, side = 'bottom', sideOffset = 6, delayDuration = 250 }) {
  if (!content) return children;
  return (
    <RadixTooltip.Root delayDuration={delayDuration}>
      <RadixTooltip.Trigger asChild>{children}</RadixTooltip.Trigger>
      <RadixTooltip.Portal>
        <RadixTooltip.Content className="ui-tooltip" side={side} sideOffset={sideOffset}>
          {content}
          <RadixTooltip.Arrow className="ui-tooltip-arrow" />
        </RadixTooltip.Content>
      </RadixTooltip.Portal>
    </RadixTooltip.Root>
  );
}
