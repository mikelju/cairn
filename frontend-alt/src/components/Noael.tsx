import React from 'react';
import { NoaelDisplay } from '../api';
import { UiText } from '../i18n';

export function noaelLabel(d: NoaelDisplay, t: UiText): string {
  if (d.state === 'pending') return t.pending;
  if (d.state === 'not_established') return t.notEstablished;
  return `${d.dose} mg/kg/day`;
}

export const NoaelPill: React.FC<{ d: NoaelDisplay; t: UiText }> = ({ d, t }) => {
  if (d.state === 'pending') return null;
  return (
    <span className={`status-pill ${d.confirmed ? '' : 'warn'}`}>
      {d.confirmed ? t.confirmed : t.saved}
    </span>
  );
};
