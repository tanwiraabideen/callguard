import { useState } from "react";

export function PasscodeForm({
  error,
  onSubmit,
}: {
  error: string;
  onSubmit: (passcode: string) => void;
}) {
  const [value, setValue] = useState("");

  return (
    <main>
      <h1>CallGuard</h1>
      <form
        id="passcode-form"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit(value);
        }}
      >
        <label htmlFor="passcode">Demo passcode </label>
        <input
          id="passcode"
          type="password"
          autoFocus
          value={value}
          onChange={(event) => setValue(event.target.value)}
        />{" "}
        <button type="submit" disabled={!value}>
          Enter
        </button>
      </form>
      {error && <p id="passcode-error">{error}</p>}
    </main>
  );
}
