/**
 * Token Service
 * Manages access token in memory with auto-refresh functionality
 */

import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class TokenService {
  private accessToken: string | null = null;
  private isRefreshing: boolean = false;
  private refreshSubscribers: ((token: string) => void)[] = [];

  /**
   * Set access token
   */
  setAccessToken(token: string, expiresIn: number): void {
    console.log('[TOKEN] Setting new access token, expires in:', expiresIn, 'seconds');
    this.accessToken = token;
  }

  /**
   * Get current access token
   */
  getAccessToken(): string | null {
    return this.accessToken;
  }

  /**
   * Clear access token
   */
  clearAccessToken(): void {
    console.log('[TOKEN] Clearing access token');
    this.accessToken = null;
  }

  /**
   * Manually refresh access token
   */
  async refreshAccessToken(): Promise<string> {
    // If already refreshing, wait for it to complete
    if (this.isRefreshing) {
      return new Promise((resolve) => {
        this.refreshSubscribers.push(resolve);
      });
    }

    this.isRefreshing = true;

    try {
      console.log('[TOKEN] Refreshing access token...');

      // Use axios directly to avoid circular dependency
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/auth/refresh`,
        {},
        { withCredentials: true }
      );

      const { access_token, expires_in } = response.data;

      this.setAccessToken(access_token, expires_in);

      console.log('[TOKEN] Token refreshed successfully');

      // Notify all waiting subscribers
      this.refreshSubscribers.forEach(callback => callback(access_token));
      this.refreshSubscribers = [];

      return access_token;
    } catch (error) {
      console.error('[TOKEN] Refresh failed:', error);
      this.refreshSubscribers = [];
      throw error;
    } finally {
      this.isRefreshing = false;
    }
  }

  /**
   * Check if token is expired
   */
  isTokenExpired(): boolean {
    if (!this.accessToken) return true;

    try {
      // Decode JWT to check expiry
      const payload = JSON.parse(atob(this.accessToken.split('.')[1]));
      const expiryTime = payload.exp * 1000;
      return Date.now() >= expiryTime;
    } catch (error) {
      console.error('[TOKEN] Failed to decode token:', error);
      return true;
    }
  }

  /**
   * Check if token needs refresh (less than 30 seconds remaining)
   */
  shouldRefreshToken(): boolean {
    if (!this.accessToken) return false;

    try {
      const payload = JSON.parse(atob(this.accessToken.split('.')[1]));
      const expiryTime = payload.exp * 1000;
      const currentTime = Date.now();
      const timeRemaining = expiryTime - currentTime;

      // Refresh if less than 30 seconds remaining
      return timeRemaining < 30000;
    } catch (error) {
      console.error('[TOKEN] Failed to decode token:', error);
      return false;
    }
  }

  /**
   * Validate current token with server
   */
  async validateToken(): Promise<boolean> {
    if (!this.accessToken) return false;

    try {
      await axios.get(`${API_BASE_URL}/api/v1/auth/check`, {
        headers: { Authorization: `Bearer ${this.accessToken}` },
        withCredentials: true
      });
      return true;
    } catch (error) {
      return false;
    }
  }
}

// Export singleton instance
export default new TokenService();
