import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}
interface State {
  error: Error | null;
}

/** Fronteira de erro de topo: evita a "tela branca" quando algo no render quebra. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error("Erro de render:", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="page">
          <div className="banner banner-error">
            <strong>Algo quebrou ao renderizar.</strong>
            <p style={{ margin: "8px 0 0" }}>{this.state.error.message}</p>
            <button
              className="primary"
              style={{ marginTop: 12 }}
              onClick={() => window.location.reload()}
            >
              Recarregar
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
