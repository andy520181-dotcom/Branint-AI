/** 邮箱脱敏展示，如 44*****17@qq.com */
export function maskEmail(email: string): string {
  const at = email.indexOf('@');
  if (at <= 0) return email;
  const local = email.slice(0, at);
  const domain = email.slice(at + 1);
  if (!local) return email;
  const len = local.length;
  if (len <= 2) return `*@${domain}`;
  if (len <= 4) return `${local[0]}${'*'.repeat(len - 1)}@${domain}`;
  const stars = Math.min(5, Math.max(3, len - 4));
  return `${local.slice(0, 2)}${'*'.repeat(stars)}${local.slice(-2)}@${domain}`;
}

export function emailLocalPart(email: string): string {
  const at = email.indexOf('@');
  return at > 0 ? email.slice(0, at) : email;
}
