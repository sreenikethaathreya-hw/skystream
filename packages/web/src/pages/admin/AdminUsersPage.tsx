import { useState } from "react";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { useSaveUser } from "@/hooks/mutations";
import { useAdminUsers } from "@/hooks/queries";
import { useSession } from "@/hooks/useSession";
import type { AdminUser, UserScope } from "@/lib/types";

const EMPTY = { email: "", name: "", role: "rep" as AdminUser["role"], active: true, scopes: "" };

const formatScopes = (scopes: UserScope[]) => scopes.map((s) => `${s.countryCode} ${s.scopeType} ${s.scopeId}`).join("\n");

function parseScopes(text: string): UserScope[] {
  return text
    .split(/\n|;/)
    .map((line) => line.trim().split(/\s+/))
    .filter((parts) => parts.length === 3 && (parts[1] === "mega" || parts[1] === "micro"))
    .map(([countryCode, scopeType, scopeId]) => ({
      countryCode: countryCode.toUpperCase(),
      scopeType: scopeType as UserScope["scopeType"],
      scopeId,
    }));
}

export function AdminUsersPage() {
  const { user } = useSession();
  const { data: users = [] } = useAdminUsers();
  const save = useSaveUser();
  const toast = useToast();
  const [form, setForm] = useState(EMPTY);

  if (user?.role !== "admin") return <p className="text-sm text-muted">Only admins can manage users.</p>;

  const onSave = () =>
    save.mutate(
      { email: form.email.trim().toLowerCase(), name: form.name.trim(), role: form.role, active: form.active, scopes: parseScopes(form.scopes) },
      {
        onSuccess: () => {
          toast({ tone: "success", title: `Saved ${form.email}` });
          setForm(EMPTY);
        },
        onError: (e) => toast({ tone: "error", title: "Could not save", body: e.message }),
      },
    );

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
      <Card>
        <CardHeader
          title={`Users (${users.length})`}
          subtitle="People sign in with Google; only listed, active users get in. Bulk changes: upload a rep assignments file."
        />
        <CardBody>
          <table className="w-full text-sm" data-testid="users-table">
            <thead className="text-left text-xs text-muted">
              <tr>
                <th className="py-1">User</th>
                <th>Role</th>
                <th>Scopes</th>
                <th>Last seen</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.email} className="border-t border-line/60 align-top">
                  <td className="py-1.5">
                    <p className="font-medium">{u.name}</p>
                    <p className="text-xs text-muted">{u.email}</p>
                  </td>
                  <td>
                    {u.role} {!u.active && <StatusBadge status="superseded" />}
                  </td>
                  <td className="whitespace-pre text-xs">{formatScopes(u.scopes) || "-"}</td>
                  <td className="text-xs">{u.lastSeenAt ? new Date(u.lastSeenAt).toLocaleDateString() : "never"}</td>
                  <td>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setForm({ email: u.email, name: u.name, role: u.role, active: u.active, scopes: formatScopes(u.scopes) })}
                    >
                      Edit
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title={form.email ? `Edit ${form.email}` : "Add a user"} />
        <CardBody className="flex flex-col gap-3 text-sm">
          <input className="h-9 rounded-lg border border-line px-2" placeholder="email@company.com" aria-label="Email"
            value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          <input className="h-9 rounded-lg border border-line px-2" placeholder="Name" aria-label="Name"
            value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <select className="h-9 rounded-lg border border-line px-2" aria-label="Role" value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value as AdminUser["role"] })}>
            <option value="rep">Rep: enters demand for assigned segments</option>
            <option value="lead">Lead: runs consensus</option>
            <option value="admin">Admin: loads data and manages users</option>
          </select>
          <label className="flex flex-col gap-1 text-xs text-muted">
            Scopes, one per line: country type id (e.g. "ES mega SP01" or "ES micro 2482")
            <textarea className="min-h-24 rounded-lg border border-line p-2 font-mono text-xs text-ink" aria-label="Scopes"
              value={form.scopes} onChange={(e) => setForm({ ...form, scopes: e.target.value })} />
          </label>
          <label className="flex items-center gap-2 text-xs">
            <input type="checkbox" checked={form.active} onChange={(e) => setForm({ ...form, active: e.target.checked })} />
            Active (unchecked users cannot sign in)
          </label>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setForm(EMPTY)}>
              Clear
            </Button>
            <Button onClick={onSave} disabled={!form.email || !form.name || save.isPending}>
              Save user
            </Button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
