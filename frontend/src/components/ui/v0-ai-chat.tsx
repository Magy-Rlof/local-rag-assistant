"use client";

import { useCallback, useEffect, useRef, type KeyboardEvent, type ReactNode } from "react";
import {
  ArrowUpIcon,
  Loader2,
} from "lucide-react";

import { Textarea } from "./textarea";
import { cn } from "../../lib/utils";

interface UseAutoResizeTextareaProps {
  minHeight: number;
  maxHeight?: number;
}

function useAutoResizeTextarea({ minHeight, maxHeight }: UseAutoResizeTextareaProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const adjustHeight = useCallback(
    (reset?: boolean) => {
      const textarea = textareaRef.current;
      if (!textarea) return;

      if (reset) {
        textarea.style.height = `${minHeight}px`;
        textarea.style.overflowY = "hidden";
        return;
      }

      textarea.style.height = `${minHeight}px`;
      const newHeight = Math.max(minHeight, Math.min(textarea.scrollHeight, maxHeight ?? Number.POSITIVE_INFINITY));
      textarea.style.height = `${newHeight}px`;
      textarea.style.overflowY = textarea.scrollHeight > newHeight ? "auto" : "hidden";
    },
    [minHeight, maxHeight]
  );

  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = `${minHeight}px`;
      textarea.style.overflowY = "hidden";
    }
  }, [minHeight]);

  useEffect(() => {
    const handleResize = () => adjustHeight();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [adjustHeight]);

  return { textareaRef, adjustHeight };
}

type VercelV0ChatProps = {
  value: string;
  onValueChange: (value: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
  loading?: boolean;
  title?: string;
  placeholder?: string;
  toolbarLeft?: ReactNode;
};

export function VercelV0Chat({
  value,
  onValueChange,
  onSubmit,
  disabled = false,
  loading = false,
  title = "问我关于简历、岗位或项目的问题",
  placeholder = "输入消息，Enter 发送，Shift+Enter 换行",
  toolbarLeft,
}: VercelV0ChatProps) {
  const { textareaRef, adjustHeight } = useAutoResizeTextarea({
    minHeight: 62,
    maxHeight: 190,
  });

  const canSubmit = Boolean(value.trim()) && !disabled && !loading;

  const handleSubmit = () => {
    if (!canSubmit) return;
    onSubmit();
    adjustHeight(true);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="v0-chat">
      {title && (
        <div className="v0-chat-hero">
          <h2>{title}</h2>
        </div>
      )}

      <div className="v0-chat-box">
        <div className="v0-chat-textarea-wrap">
          <Textarea
            ref={textareaRef}
            value={value}
            onChange={(event) => {
              onValueChange(event.target.value);
              adjustHeight();
            }}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            className="v0-chat-textarea"
          />
        </div>

        <div className="v0-chat-toolbar">
          <div className="v0-chat-toolbar-left">{toolbarLeft}</div>
          <button
            className={cn("v0-chat-send", canSubmit && "is-ready")}
            type="button"
            onClick={handleSubmit}
            disabled={!canSubmit}
            aria-label="发送消息"
            title="发送消息"
          >
            {loading ? <Loader2 className="spin" size={17} /> : <ArrowUpIcon size={18} />}
          </button>
        </div>
      </div>

    </div>
  );
}
