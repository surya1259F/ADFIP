import React from 'react';
import { Link } from 'react-router-dom';
import { Shield, ArrowLeft } from 'lucide-react';
import { Button } from '../../components/ui/Button';

export const TermsPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-stone-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto bg-white border border-stone-200 rounded-xl shadow-sm p-8 sm:p-12">
        {/* Top Header */}
        <div className="flex items-center justify-between border-b border-stone-100 pb-6 mb-8">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-slate-900 rounded-lg">
              <Shield className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900">ADFIP Terms of Service</h1>
              <p className="text-xs text-slate-500">
                Autonomous Digital Forensics Investigation Platform
              </p>
            </div>
          </div>
          <Link to="/signin">
            <Button variant="outline" size="sm" icon={<ArrowLeft className="w-3.5 h-3.5" />}>
              Back
            </Button>
          </Link>
        </div>

        <div className="text-xs text-slate-400 mb-6">
          Last Updated: October 3, 2026 • Version 1.2
        </div>

        {/* Content */}
        <div className="space-y-6 text-sm text-slate-700 leading-relaxed">
          <section>
            <h2 className="text-base font-semibold text-slate-900 mb-2">1. Service Definition</h2>
            <p>
              The Autonomous Digital Forensics Investigation Platform ("ADFIP") is a forensic investigation workstation and orchestrator designed to assist authorized law enforcement, security incident response teams, and forensic analysts in acquiring, verifying, analyzing, and reporting digital evidence.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900 mb-2">2. User Responsibilities & RBAC</h2>
            <p>
              Access to ADFIP is restricted to authorized personnel who have been granted access credentials by an organization administrator. Users are responsible for maintaining the confidentiality of their credentials and all session activity performed under their account.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900 mb-2">3. Authorized Evidence Use</h2>
            <p>
              Users may only ingest, preserve, and examine digital evidence that they are legally authorized to inspect by statutory authority, search warrant, court order, explicit organizational consent, or applicable contractual agreements. ADFIP must not be used on unauthorized systems or unapproved data.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900 mb-2">4. Evidence Handling & Chain of Custody</h2>
            <p>
              ADFIP enforces strict forensic integrity and chain-of-custody logging adhering to ISO/IEC 27037 standards. Digital evidence sources are registered with immutable cryptographic hashes (SHA-256 and MD5). Users must verify that source hashes match prior to commencing analytical procedures.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900 mb-2">5. AI-Assisted Analysis & Human Verification</h2>
            <p>
              ADFIP incorporates autonomous reasoning agents to correlate artifacts, construct timelines, and propose investigation hypotheses. However, AI reasoning is <strong>downstream</strong> of verified forensic tool outputs. AI-generated insights are labeled as inferences and require human investigator review and explicit verification before inclusion in certified final reports.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900 mb-2">6. Deterministic Tool Execution</h2>
            <p>
              Underlying forensic analysis relies on deterministic command-line adapters (such as The Sleuth Kit, Volatility 3, YARA, and python-evtx). Tool execution logs, exit codes, and raw tool outputs are recorded for defensible auditability.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900 mb-2">7. Account Responsibilities & Credential Security</h2>
            <p>
              Plaintext passwords and third-party AI provider API keys are never stored in browser local storage or persistent cookies. Session tokens are maintained strictly within active browser session storage and invalidated upon logout or timeout.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900 mb-2">8. Security & Audit Logging</h2>
            <p>
              All case creation, evidence intake, plan recalculation, tool execution, report generation, and user login events are immutably logged to the ADFIP system audit log with actor ID, timestamp, and action detail.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900 mb-2">9. Service Availability & Local Execution</h2>
            <p>
              ADFIP can operate in fully air-gapped or local environments with local reasoning templates and local tool engines. External cloud LLM providers are optional and subject to the organization’s network egress policies.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900 mb-2">10. Modifications to Terms</h2>
            <p>
              Organizational administrators and platform maintainers reserve the right to update these terms to maintain alignment with applicable digital forensics legal frameworks and accreditation standards.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900 mb-2">11. Contact & Agency Support</h2>
            <p>
              For legal compliance questions, evidence integrity issues, or platform support, contact your designated agency digital forensics unit supervisor or IT security administrator.
            </p>
          </section>
        </div>

        <div className="mt-10 pt-6 border-t border-stone-100 flex items-center justify-between text-xs text-slate-400">
          <span>ADFIP Forensic Platform</span>
          <div className="flex gap-4">
            <Link to="/privacy" className="hover:text-slate-600 underline">
              Privacy Policy
            </Link>
            <Link to="/signin" className="hover:text-slate-600 underline">
              Sign In
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
