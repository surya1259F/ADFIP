import React from 'react';
import type { Evidence } from '../types';
import { EvidenceItem } from './EvidenceItem';
import { EmptyState } from './EmptyState';
import { HardDrive } from 'lucide-react';

interface EvidenceListProps {
  evidenceList: Evidence[];
  selectedId?: string;
  onSelectEvidence: (ev: Evidence) => void;
  onIntakeClick?: () => void;
}

export const EvidenceList: React.FC<EvidenceListProps> = ({
  evidenceList,
  selectedId,
  onSelectEvidence,
  onIntakeClick,
}) => {
  if (evidenceList.length === 0) {
    return (
      <EmptyState
        icon={HardDrive}
        title="No Evidence Ingested"
        description="Add a forensic image, memory dump, or log file to begin investigation."
        actionLabel="Intake Evidence"
        onAction={onIntakeClick}
      />
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {evidenceList.map((ev) => (
        <EvidenceItem
          key={ev.id}
          evidence={ev}
          isSelected={ev.id === selectedId}
          onSelect={() => onSelectEvidence(ev)}
        />
      ))}
    </div>
  );
};
