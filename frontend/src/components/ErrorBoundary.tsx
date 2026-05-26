import { Component, ErrorInfo, ReactNode } from 'react';
import { EuiCallOut, EuiCodeBlock } from '@elastic/eui';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      error,
      errorInfo: null,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    this.setState({
      error,
      errorInfo,
    });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '40px', maxWidth: '800px', margin: '0 auto' }}>
          <EuiCallOut
            title="Something went wrong"
            color="danger"
            iconType="alert"
          >
            <p>This page encountered an error:</p>
            {this.state.error && (
              <EuiCodeBlock language="text" fontSize="s" paddingSize="s">
                {this.state.error.toString()}
                {this.state.errorInfo && (
                  <>
                    {'\n\n'}
                    {this.state.errorInfo.componentStack}
                  </>
                )}
              </EuiCodeBlock>
            )}
          </EuiCallOut>
        </div>
      );
    }

    return this.props.children;
  }
}

