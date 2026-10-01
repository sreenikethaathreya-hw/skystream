import { NavLink } from "react-router-dom";
import { ArrowUpRight, CheckCircle2, Download } from "lucide-react";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import type { ChatAction, ChatDownload } from "@/lib/types";

/** What the assistant changed, with a link to see it on its page. */
export function ActionReceipt({ action }: { action: ChatAction }) {
  return (
    <div
      className="mt-2 flex items-start gap-2 rounded-lg border border-brand-500/30 bg-brand-50 px-3 py-2 text-xs text-brand-700"
      data-testid="chat-action"
      data-kind={action.kind}
    >
      <CheckCircle2 size={14} className="mt-0.5 shrink-0" />
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="font-medium">Done: {action.summary}</span>
        {action.link && action.link.startsWith("/") && !action.link.startsWith("//") && (
          <NavLink to={action.link} className="inline-flex items-center gap-1 font-medium hover:underline">
            See it <ArrowUpRight size={12} />
          </NavLink>
        )}
      </div>
    </div>
  );
}

export function DownloadLink({ download }: { download: ChatDownload }) {
  const toast = useToast();
  if (!download.href.startsWith("/export/")) return null;
  const filename = download.href.split("?")[0].split("/").pop() ?? "download.csv";
  return (
    <button
      type="button"
      className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-brand-700 hover:underline"
      data-testid="chat-download"
      onClick={() =>
        api
          .download(download.href, filename)
          .catch((e: Error) => toast({ tone: "error", title: "Download failed", body: e.message }))
      }
    >
      <Download size={12} /> {download.label}
    </button>
  );
}
