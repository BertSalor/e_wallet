window.FinanceAPI = {
  async request(path, options={}) {
    const response = await fetch((window.FINANCE_CONFIG?.API_BASE || "/api") + path, {credentials:"same-origin", headers:{"Content-Type":"application/json", ...(options.headers||{})}, ...options});
    const payload = await response.json().catch(()=>({success:false,error:"Invalid server response"}));
    if (!response.ok || !payload.success) throw new Error(payload.error || "Request failed");
    return payload.data;
  }
};
