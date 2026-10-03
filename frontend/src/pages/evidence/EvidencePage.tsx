import React, { useState, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Inbox,
  Plus,
  UploadCloud,
  HardDrive,
  AlertCircle,
  FileCheck,
} from 'lucide-react';
import { evidenceService } from '../../services/evidence';
import { normalizeError } from '../../services/client';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { StatusBadge, Badge } from '../../components/ui/Badge';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { SkeletonRow } from '../../components/ui/Skeleton';
import { Dialog } from '../../components/ui/Dialog';
import { Input } from '../../components/ui/Input';
import { Select } from '../../components/ui/Select';
import { SectionHeader } from '../../components/ui/SectionHeader';
import { HashDisplay } from '../../components/ui/HashDisplay';
import { formatFileSize } from '../../lib/utils';
import type { Evidence } from '../../types';

const EVIDENCE_TYPES = [
  { value: 'disk_image', label: 'Disk Image (.dd, .raw, .e01, .vmdk)' },
  { value: 'memory_dump', label: 'Memory Dump (.raw, .vmem, .dmp)' },
  { value: 'log_file', label: 'Security / Audit Logs (.evtx, .log, .json)' },
  { value: 'network_capture', label: 'Network Capture (.pcap, .pcapng)' },
  { value: 'document', label: 'Document File (.docx, .doc, .pdf, .txt, .odt)' },
  { value: 'file', label: 'Single File / Artifact' },
  { value: 'directory', label: 'Directory of Files' },
  { value: 'other', label: 'Other Forensics Data' },
];

const detectEvidenceType = (fileName: string): string => {
  const lower = fileName.toLowerCase();
  if (
    lower.endsWith('.dd') ||
    lower.endsWith('.raw') ||
    lower.endsWith('.img') ||
    lower.endsWith('.e01') ||
    lower.endsWith('.vmdk') ||
    lower.endsWith('.aff4')
  ) {
    return 'disk_image';
  }
  if (
    lower.endsWith('.vmem') ||
    lower.endsWith('.dmp') ||
    lower.endsWith('.lime') ||
    lower.endsWith('.core') ||
    lower.includes('memory')
  ) {
    return 'memory_dump';
  }
  if (
    lower.endsWith('.evtx') ||
    lower.endsWith('.log') ||
    lower.endsWith('.audit') ||
    lower.includes('event')
  ) {
    return 'log_file';
  }
  if (
    lower.endsWith('.pcap') ||
    lower.endsWith('.pcapng') ||
    lower.endsWith('.cap')
  ) {
    return 'network_capture';
  }
  if (
    lower.endsWith('.docx') ||
    lower.endsWith('.doc') ||
    lower.endsWith('.pdf') ||
    lower.endsWith('.txt') ||
    lower.endsWith('.rtf') ||
    lower.endsWith('.odt') ||
    lower.endsWith('.xlsx') ||
    lower.endsWith('.pptx')
  ) {
    return 'document';
  }
  return 'file';
};

interface SelectedFileInfo {
  name: string;
  size?: number;
  path: string;
  type: string;
}

const AddEvidenceDialog: React.FC<{
  open: boolean;
  onClose: () => void;
  caseId: string;
}> = ({ open, onClose, caseId }) => {
  const qc = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [selectedFile, setSelectedFile] = useState<SelectedFileInfo | null>(null);
  const [evidenceType, setEvidenceType] = useState<string>('disk_image');
  const [notes, setNotes] = useState('');
  const [manualPathOverride, setManualPathOverride] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => {
      const targetPath = manualPathOverride.trim();
      const targetName = selectedFile?.name || targetPath.split(/[/\\]/).pop() || targetPath;

      return evidenceService.intake(caseId, {
        name: targetName,
        file_path: targetPath,
        source_path: targetPath,
        evidence_type: evidenceType,
        notes: notes.trim() || undefined,
        case_id: caseId,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['cases', caseId, 'evidence'] });
      resetForm();
      onClose();
    },
    onError: (e) => {
      const msg = normalizeError(e);
      if (msg.includes('not found on disk') || msg.toLowerCase().includes('file not found')) {
        setErr('The selected evidence file could not be found at the supplied path. Verify that the file exists and the path is accessible to the backend workstation.');
      } else {
        setErr(msg);
      }
    },
  });

  const resetForm = () => {
    setSelectedFile(null);
    setEvidenceType('disk_image');
    setNotes('');
    setManualPathOverride('');
    setErr(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleFileChosen = (file: File) => {
    const detected = detectEvidenceType(file.name);
    const nativePath = (file as any).path || '';
    setSelectedFile({
      name: file.name,
      size: file.size,
      path: nativePath,
      type: detected,
    });
    setEvidenceType(detected);
    if (nativePath) {
      setManualPathOverride(nativePath);
    }
    setErr(null);
  };

  const handleNativeBrowse = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileChosen(e.dataTransfer.files[0]);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const targetPath = manualPathOverride.trim();
    if (!targetPath) {
      if (selectedFile) {
        setErr(`Please enter the complete host filesystem path for "${selectedFile.name}" (e.g., /path/to/${selectedFile.name}). In browser environments, full local paths must be specified.`);
      } else {
        setErr('Please select an evidence file or provide a source file path.');
      }
      return;
    }
    if (!targetPath.includes('/') && !targetPath.includes('\\')) {
      setErr(`Please specify the full filesystem path on the host for "${targetPath}" (e.g., /path/to/${targetPath}).`);
      return;
    }
    mutation.mutate();
  };

  return (
    <Dialog
      open={open}
      onClose={() => {
        resetForm();
        onClose();
      }}
      title="Register Evidence"
      description="Preserve digital evidence in the case vault. Immutable SHA-256 integrity hashes are computed upon registration."
      size="md"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {err && (
          <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-xs flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
            <span>{err}</span>
          </div>
        )}

        {/* Hidden HTML5 File Input for Browser / Native File Picker */}
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          onChange={(e) => {
            if (e.target.files && e.target.files[0]) {
              handleFileChosen(e.target.files[0]);
            }
          }}
        />

        {/* Primary Interaction: Browse / Select Evidence Card */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-xl p-5 text-center transition-colors ${
            isDragging
              ? 'border-slate-800 bg-stone-100/70'
              : 'border-stone-200 hover:border-stone-300 bg-stone-50/50'
          }`}
        >
          <div className="mx-auto w-10 h-10 rounded-full bg-white border border-stone-200 flex items-center justify-center text-slate-700 mb-3 shadow-xs">
            <UploadCloud className="w-5 h-5" />
          </div>

          <div className="space-y-1 mb-3">
            <p className="text-xs font-semibold text-slate-800">Select source evidence for examination</p>
            <p className="text-[11px] text-slate-500">
              Disk images, memory captures, event log files, or raw artifacts
            </p>
          </div>

          <Button
            type="button"
            variant="primary"
            size="sm"
            onClick={handleNativeBrowse}
            icon={<HardDrive className="w-3.5 h-3.5" />}
          >
            Browse / Select Evidence
          </Button>

          <p className="text-[10px] text-slate-400 mt-2">
            or drag and drop evidence files here
          </p>
        </div>

        {/* Selected Evidence Details Display */}
        {selectedFile && (
          <div className="p-3.5 bg-stone-100/60 border border-stone-200 rounded-lg space-y-2 text-xs">
            <div className="flex items-center justify-between border-b border-stone-200/60 pb-2">
              <span className="text-slate-500 font-medium">Selected Evidence:</span>
              <span className="font-mono font-semibold text-slate-900 truncate max-w-[240px]">
                {selectedFile.name}
              </span>
            </div>

            {selectedFile.size !== undefined && selectedFile.size > 0 && (
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Evidence Size:</span>
                <span className="font-mono text-slate-700">{formatFileSize(selectedFile.size)}</span>
              </div>
            )}

            <div className="flex items-center justify-between">
              <span className="text-slate-500">Detected Format:</span>
              <Badge tone="info">
                {selectedFile.type === 'document'
                  ? 'DOCUMENT FILE'
                  : selectedFile.type.replace('_', ' ').toUpperCase()}
              </Badge>
            </div>
          </div>
        )}

        {/* Evidence Type Selection */}
        <Select
          label="Evidence Type"
          value={evidenceType}
          onChange={(e) => setEvidenceType(e.target.value)}
          options={EVIDENCE_TYPES}
        />

        {/* Source Path Input (Populated by File Picker or Manual Absolute Path) */}
        <Input
          label="Source File Path"
          value={manualPathOverride}
          onChange={(e) => {
            setManualPathOverride(e.target.value);
            if (err) setErr(null);
          }}
          placeholder="/path/to/evidence/sample.docx or C:\Evidence\image.raw"
          helper={
            selectedFile && !selectedFile.path
              ? `Web browser mode: enter the complete filesystem path on the host where "${selectedFile.name}" is located.`
              : 'Absolute filesystem path accessible to the ADFIP backend workstation.'
          }
          required
        />

        {/* Optional Notes */}
        <Input
          label="Acquisition Notes (Optional)"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="e.g. Primary forensic copy acquired from workstation #3"
        />

        {/* Dialog Actions */}
        <div className="flex justify-end gap-2 pt-2 border-t border-stone-100">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => {
              resetForm();
              onClose();
            }}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            size="sm"
            loading={mutation.isPending}
            icon={<FileCheck className="w-3.5 h-3.5" />}
          >
            Register Evidence
          </Button>
        </div>
      </form>
    </Dialog>
  );
};

export const EvidencePage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const [addOpen, setAddOpen] = useState(false);

  const { data: evidence, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['cases', caseId, 'evidence'],
    queryFn: () => evidenceService.listByCase(caseId!),
    enabled: !!caseId,
  });

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <SectionHeader
        title="Evidence Registry"
        description="Preserved digital evidence items, cryptographic hashes, and chain of custody for this investigation."
        action={
          <Button
            variant="primary"
            size="sm"
            icon={<Plus className="w-3.5 h-3.5" />}
            onClick={() => setAddOpen(true)}
          >
            Register Evidence
          </Button>
        }
      />

      {isError && (
        <ErrorState message={normalizeError(error)} onRetry={refetch} />
      )}

      {isLoading && (
        <Card padding={false}>
          {[1, 2, 3].map((i) => (
            <SkeletonRow key={i} cols={6} />
          ))}
        </Card>
      )}

      {!isLoading && !isError && (evidence?.length ?? 0) === 0 && (
        <EmptyState
          icon={<Inbox className="w-10 h-10" />}
          title="No evidence registered yet"
          description="Register your first evidence source to calculate cryptographic hashes and begin investigation."
          action={
            <Button
              variant="primary"
              size="sm"
              icon={<HardDrive className="w-3.5 h-3.5" />}
              onClick={() => setAddOpen(true)}
            >
              Browse / Select Evidence
            </Button>
          }
        />
      )}

      {!isLoading && !isError && (evidence?.length ?? 0) > 0 && (
        <Card padding={false} className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="bg-stone-50/80 border-b border-stone-200/80 text-slate-500 font-medium">
                  <th className="px-4 py-2.5">Evidence Identifier</th>
                  <th className="px-4 py-2.5">Type</th>
                  <th className="px-4 py-2.5">Size</th>
                  <th className="px-4 py-2.5">SHA-256 Hash</th>
                  <th className="px-4 py-2.5">Integrity</th>
                  <th className="px-4 py-2.5">Status</th>
                  <th className="px-4 py-2.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100">
                {evidence!.map((ev: Evidence) => (
                  <tr
                    key={ev.id}
                    className="hover:bg-stone-50/50 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <p className="font-medium text-slate-900 text-sm font-mono">
                        {ev.name}
                      </p>
                      <p className="font-mono text-[10px] text-slate-400 mt-0.5">
                        ID: {ev.id.slice(0, 8).toUpperCase()}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-slate-600 font-mono text-[11px] uppercase">
                      {ev.evidence_type}
                    </td>
                    <td className="px-4 py-3 text-slate-600 font-mono">
                      {ev.size_bytes != null
                        ? formatFileSize(ev.size_bytes)
                        : '—'}
                    </td>
                    <td className="px-4 py-3">
                      {ev.sha256 || ev.sha256_hash ? (
                        <HashDisplay hash={ev.sha256 || ev.sha256_hash || ''} />
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {ev.verification_status || ev.integrity_status ? (
                        <StatusBadge status={ev.verification_status || ev.integrity_status || 'VERIFIED'} />
                      ) : (
                        <Badge tone="neutral">Unverified</Badge>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={ev.status || 'REGISTERED'} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link to={`/cases/${caseId}/evidence/${ev.id}`}>
                        <Button size="sm" variant="ghost">
                          View Details
                        </Button>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {caseId && (
        <AddEvidenceDialog
          open={addOpen}
          onClose={() => setAddOpen(false)}
          caseId={caseId}
        />
      )}
    </div>
  );
};
