"use client";

import { useId, useState } from "react";

type Props = {
  label: string;
  name: string;
  autoComplete: string;
  minLength?: number;
  maxLength?: number;
  hint?: string;
};

export function PasswordField({ label, name, autoComplete, minLength, maxLength, hint }: Props) {
  const id = useId();
  const [visible, setVisible] = useState(false);

  return <div className="password-field">
    <label htmlFor={id}>{label}</label>
    <div className="password-control">
      <input id={id} name={name} type={visible ? "text" : "password"} required minLength={minLength} maxLength={maxLength} autoComplete={autoComplete} />
      <button type="button" aria-label={`${visible ? "Hide" : "Show"} ${label.toLowerCase()}`} aria-pressed={visible} onClick={() => setVisible((current) => !current)}>{visible ? "Hide" : "Show"}</button>
    </div>
    {hint && <small>{hint}</small>}
  </div>;
}
