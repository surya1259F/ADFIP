import React from 'react';
import { Link } from 'react-router-dom';
import { Shield, ArrowLeft } from 'lucide-react';
import { Button } from '../../components/ui/Button';

export const PrivacyPage: React.FC = () => {
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
              <h1 className="text-xl font-bold text-slate-900">ADFIP Privacy Policy</h1>
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
            <h2 className="text-base font-semibold text-slate-900 mb-2">1. Information Collected</h2>
            <p>
              ADFIP collects only information strictly necessary to perform authorized forensic investigations and maintain legal defensibility under criminal and civil evidentiary standards.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900 mb-2">2. Account Information</h2>
            <p>
              We collect user profile data including work email, full name, agency or organization affiliation, investigator badge/employee ID, and salted cryptographic password hashes. Plaintext passwords are never recorded or accessible.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900 mb-2">3. Case & Investigation Information</h2>
            <p>
              Case identifiers, investigation titles, scope descriptions, chain-of-custody transfer logs, forensic notes, and verification decisions are stored in the application database and isolated according to organizational case access controls.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900 mb-2">4. Evidence Handling & Storage Isolation</h2>
            <p>
              Forensic image files (such as disk images, memory captures, network pcap files, and log files) reside on the local workstation or designated secure evidence vault. Raw evidence files are not transmitted to third parties without explicit investigator instruction and egress policy approval.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900 mb-2">5. AI Reasoning Providers & Egress Policy</h2>
            <p>
              When AI-assisted reasoning is enabled, investigator-approved prompt fragments may be routed to the configured provider (e.g., Google Gemini, OpenAI, Anthropic, or a Local Ollama/OpenAI instance). Organizations may enforce <code>LOCAL_ONLY</code> or <code>EXTERNAL_PROVIDER_BLOCKED</code> policies to ensure all processing remains local to the organization.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900 mb-2">6. API Keys & Credential Encryption</h2>
            <p>
              User-configured AI provider API keys are encrypted at rest using AES-GCM encryption on the backend server. API keys are never stored in browser storage (localStorage, sessionStorage, or cookies) and are masked when displayed in administrative interfaces.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900 mb-2">7. Authentication Credentials & Tokens</h2>
            <p>
              JWT session tokens are stored exclusively in active browser session memory (sessionStorage) and transmitted only via HTTPS Bearer authorization headers. Tokens are revoked upon sign-out and tracked in the revoked tokens registry.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900 mb-2">8. Local Application Storage</h2>
            <p>
              The client interface stores only transient UI presentation state (such as sidebar collapse preference and active tab selection). No evidentiary artifacts or findings are stored in insecure browser caches.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900 mb-2">9. Security & Access Logging</h2>
            <p>
              Every action taken within the platform is recorded with the authenticated investigator identity, IP address, timestamp, and action summary to preserve audit integrity for legal proceedings.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900 mb-2">10. Data Retention & Deletion</h2>
            <p>
              Case records and evidence retention timelines are governed by organizational data retention policies and statutory requirements. Closed or archived cases remain immutable until expunged by an authorized system administrator.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900 mb-2">11. Third-Party Services</h2>
            <p>
              ADFIP does not integrate tracking analytics, third-party advertising, or commercial data brokers. External connections are limited strictly to user-configured AI providers and software update repositories if enabled.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900 mb-2">12. User Rights & Data Protection</h2>
            <p>
              Investigators and subjects retain rights to data accuracy and audit transparency in accordance with applicable evidentiary disclosure rules and jurisdiction privacy standards.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900 mb-2">13. Privacy Inquiries</h2>
            <p>
              For questions regarding the ADFIP privacy architecture or data security controls, contact your agency forensics laboratory director or platform administrator.
            </p>
          </section>
        </div>

        <div className="mt-10 pt-6 border-t border-stone-100 flex items-center justify-between text-xs text-slate-400">
          <span>ADFIP Forensic Platform</span>
          <div className="flex gap-4">
            <Link to="/terms" className="hover:text-slate-600 underline">
              Terms of Service
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
