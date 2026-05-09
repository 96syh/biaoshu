import { CheckCircleIcon, XMarkIcon } from '@heroicons/react/24/outline';

export const VerifyLine = ({ ok, label }: { ok?: boolean; label: string }) => (
  <div className="verify-line">
    {ok === undefined ? (
      <span className="verify-line__pending" />
    ) : ok ? (
      <CheckCircleIcon className="h-4 w-4 text-emerald-600" />
    ) : (
      <XMarkIcon className="h-4 w-4 text-rose-600" />
    )}
    <span>{label}</span>
  </div>
);
