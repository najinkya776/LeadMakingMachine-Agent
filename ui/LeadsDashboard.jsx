import { useState, useEffect } from 'react';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import './LeadsDashboard.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

const STATUS_COLORS = {
  new: '#6366f1',
  scraped: '#8b5cf6',
  qualified: '#a855f7',
  audited: '#d946ef',
  scored: '#ec4899',
  report_generated: '#f43f5e',
  contacted: '#f97316',
  responded: '#eab308',
  interested: '#84cc16',
  negotiating: '#22c55e',
  converted: '#10b981',
  trashed: '#6b7280',
  bounced: '#ef4444',
  unsubscribed: '#dc2626',
};

const STATUS_LABELS = {
  new: 'New',
  scraped: 'Scraped',
  qualified: 'Qualified',
  audited: 'Audited',
  scored: 'Scored',
  report_generated: 'Report Sent',
  contacted: 'Contacted',
  responded: 'Responded',
  interested: 'Interested',
  negotiating: 'Negotiating',
  converted: 'Converted',
  trashed: 'Trashed',
  bounced: 'Bounced',
  unsubscribed: 'Unsubscribed',
};

export default function LeadsDashboard() {
  const [leads, setLeads] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ status: '', industry: '', search: '' });
  const [selectedLead, setSelectedLead] = useState(null);
  const [activeTab, setActiveTab] = useState('leads');

  useEffect(() => {
    fetchStats();
    fetchLeads();
  }, []);

  useEffect(() => {
    fetchLeads();
  }, [filter.status, filter.industry]);

  const fetchStats = async () => {
    try {
      const res = await fetch(`${API_URL}/api/leads/stats`);
      const data = await res.json();
      setStats(data);
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  };

  const fetchLeads = async () => {
    setLoading(true);
    try {
      let url = `${API_URL}/api/leads?limit=100`;
      if (filter.status) url += `&status=${filter.status}`;
      if (filter.industry) url += `&industry=${filter.industry}`;
      const res = await fetch(url);
      const data = await res.json();
      setLeads(data);
    } catch (err) {
      console.error('Failed to fetch leads:', err);
    }
    setLoading(false);
  };

  const searchLeads = async (query) => {
    if (!query) {
      fetchLeads();
      return;
    }
    try {
      const res = await fetch(`${API_URL}/api/leads/search?q=${encodeURIComponent(query)}`);
      const data = await res.json();
      setLeads(data);
    } catch (err) {
      console.error('Search failed:', err);
    }
  };

  const updateLeadStatus = async (leadId, newStatus) => {
    try {
      await fetch(`${API_URL}/api/leads/${leadId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      });
      fetchLeads();
      fetchStats();
    } catch (err) {
      console.error('Update failed:', err);
    }
  };

  const trashLead = async (leadId) => {
    if (!confirm('Move this lead to trash?')) return;
    try {
      await fetch(`${API_URL}/api/leads/${leadId}/trash`, { method: 'DELETE' });
      fetchLeads();
      fetchStats();
    } catch (err) {
      console.error('Trash failed:', err);
    }
  };

  const exportToCSV = () => {
    const headers = ['Business Name', 'Owner', 'Industry', 'Location', 'Email', 'Phone', 'Score', 'Status', 'Contact Attempts'];
    const csvRows = [headers.join(',')];

    leads.forEach(lead => {
      const row = [
        `"${(lead.business_name || '').replace(/"/g, '""')}"`,
        `"${(lead.owner_name || '').replace(/"/g, '""')}"`,
        `"${(lead.industry || '').replace(/"/g, '""')}"`,
        `"${(lead.location || '').replace(/"/g, '""')}"`,
        `"${(lead.email || '').replace(/"/g, '""')}"`,
        `"${(lead.phone || '').replace(/"/g, '""')}"`,
        lead.score || '',
        STATUS_LABELS[lead.status] || lead.status || '',
        lead.contact_attempts || 0
      ];
      csvRows.push(row.join(','));
    });

    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `leads_export_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const getFilteredLeads = () => {
    switch (activeTab) {
      case 'untouchable':
        return leads.filter(l => l.score >= 80 && (!l.contact_attempts || l.contact_attempts === 0));
      case 'followup':
        return leads.filter(l => l.status === 'contacted' || l.status === 'responded');
      case 'interested':
        return leads.filter(l => l.status === 'interested' || l.status === 'negotiating');
      case 'trashed':
        return leads.filter(l => l.status === 'trashed');
      default:
        return leads.filter(l => l.status !== 'trashed');
    }
  };

  const getStatusChartData = () => {
    const statusCounts = {};
    leads.filter(l => l.status !== 'trashed').forEach(l => {
      const label = STATUS_LABELS[l.status] || l.status;
      statusCounts[label] = (statusCounts[label] || 0) + 1;
    });
    return Object.entries(statusCounts).map(([name, value]) => ({
      name,
      value,
      fill: STATUS_COLORS[Object.entries(STATUS_LABELS).find(([, v]) => v === name)?.[0]] || '#6b7280'
    }));
  };

  const getIndustryChartData = () => {
    const industryCounts = {};
    leads.filter(l => l.status !== 'trashed' && l.industry).forEach(l => {
      industryCounts[l.industry] = (industryCounts[l.industry] || 0) + 1;
    });
    return Object.entries(industryCounts)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 8);
  };

  const industries = [...new Set(leads.map(l => l.industry).filter(Boolean))];
  const filteredLeads = getFilteredLeads();

  const openWhatsApp = (lead) => {
    const phone = lead.phone?.replace(/\s/g, '').replace(/[^0-9]/g, '');
    if (phone) {
      window.open(`https://wa.me/${phone}`, '_blank');
    }
  };

  const openEmail = (lead) => {
    window.location.href = `mailto:${lead.email}`;
  };

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>PrismaticWorks Lead Tracker</h1>
        <div className="header-actions">
          <button onClick={exportToCSV} className="btn-export">
            Export CSV
          </button>
          <button onClick={() => { fetchLeads(); fetchStats(); }} className="btn-refresh">
            Refresh
          </button>
        </div>
      </header>

      {/* Stats Cards */}
      {stats && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-value">{stats.total_leads}</div>
            <div className="stat-label">Total Leads</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.emails_sent}</div>
            <div className="stat-label">Emails Sent</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.replies}</div>
            <div className="stat-label">Replies ({stats.reply_rate?.toFixed(1)}%)</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.interested_leads}</div>
            <div className="stat-label">Interested</div>
          </div>
          <div className="stat-card success">
            <div className="stat-value">{stats.conversions}</div>
            <div className="stat-label">Converted ({(stats.conversion_rate || 0).toFixed(1)}%)</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">₹{stats.revenue?.toLocaleString() || 0}</div>
            <div className="stat-label">Revenue</div>
          </div>
          <div className="stat-card warning">
            <div className="stat-value">{stats.needs_followup}</div>
            <div className="stat-label">Needs Follow-up</div>
          </div>
          <div className="stat-card untouchable">
            <div className="stat-value">{stats.untouched}</div>
            <div className="stat-label">Untouched</div>
          </div>
        </div>
      )}

      {/* Charts Section */}
      {leads.length > 0 && activeTab === 'leads' && (
        <div className="charts-section">
          <div className="chart-container">
            <h3>Lead Status Distribution</h3>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={getStatusChartData()}
                  cx="50%"
                  cy="50%"
                  innerRadius={40}
                  outerRadius={80}
                  paddingAngle={2}
                  dataKey="value"
                  label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                  labelLine={false}
                >
                  {getStatusChartData().map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="chart-container">
            <h3>Leads by Industry</h3>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={getIndustryChartData()} layout="vertical">
                <XAxis type="number" />
                <YAxis type="category" dataKey="name" width={100} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="value" fill="#6366f1" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="tabs">
        <button className={activeTab === 'leads' ? 'active' : ''} onClick={() => setActiveTab('leads')}>
          All Leads
        </button>
        <button className={activeTab === 'untouchable' ? 'active' : ''} onClick={() => setActiveTab('untouchable')}>
          Untouchable Leads
        </button>
        <button className={activeTab === 'followup' ? 'active' : ''} onClick={() => setActiveTab('followup')}>
          Needs Follow-up
        </button>
        <button className={activeTab === 'interested' ? 'active' : ''} onClick={() => setActiveTab('interested')}>
          Interested
        </button>
        <button className={activeTab === 'trashed' ? 'active' : ''} onClick={() => setActiveTab('trashed')}>
          Trash
        </button>
      </div>

      {/* Filters */}
      <div className="filters">
        <input
          type="text"
          placeholder="Search by name, email, owner..."
          onChange={(e) => setFilter({...filter, search: e.target.value})}
          onKeyDown={(e) => e.key === 'Enter' && searchLeads(filter.search)}
          className="search-input"
        />
        <button onClick={() => searchLeads(filter.search)}>Search</button>
        <select
          value={filter.status}
          onChange={(e) => setFilter({...filter, status: e.target.value})}
        >
          <option value="">All Statuses</option>
          {Object.entries(STATUS_LABELS).map(([key, label]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>
        <select
          value={filter.industry}
          onChange={(e) => setFilter({...filter, industry: e.target.value})}
        >
          <option value="">All Industries</option>
          {industries.map(ind => (
            <option key={ind} value={ind}>{ind}</option>
          ))}
        </select>
      </div>

      {/* Leads Table */}
      <div className="leads-container">
        <table className="leads-table">
          <thead>
            <tr>
              <th>Business</th>
              <th>Industry</th>
              <th>Location</th>
              <th>Email</th>
              <th>Score</th>
              <th>Status</th>
              <th>Contacted</th>
              <th>Quick Actions</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan="9" className="loading">Loading...</td></tr>
            ) : filteredLeads.length === 0 ? (
              <tr><td colSpan="9" className="empty">No leads found</td></tr>
            ) : (
              filteredLeads.map(lead => (
                <tr key={lead.id} className={lead.status === 'trashed' ? 'trashed' : ''}>
                  <td>
                    <div className="business-name">{lead.business_name}</div>
                    {lead.owner_name && <div className="owner">{lead.owner_name}</div>}
                  </td>
                  <td>{lead.industry}</td>
                  <td>{lead.location}</td>
                  <td>
                    <a href={`mailto:${lead.email}`}>{lead.email}</a>
                    {lead.phone && <div className="phone">{lead.phone}</div>}
                  </td>
                  <td>
                    <div className={`score score-${lead.score >= 80 ? 'high' : lead.score >= 50 ? 'medium' : 'low'}`}>
                      {lead.score || '-'}
                    </div>
                  </td>
                  <td>
                    <span
                      className="status-badge"
                      style={{ backgroundColor: STATUS_COLORS[lead.status] || '#6b7280' }}
                    >
                      {STATUS_LABELS[lead.status] || lead.status}
                    </span>
                  </td>
                  <td>
                    {lead.contact_attempts > 0 ? (
                      <span className="contact-count">{lead.contact_attempts}x</span>
                    ) : (
                      <span className="not-contacted">Never</span>
                    )}
                  </td>
                  <td>
                    <div className="quick-actions">
                      {lead.phone && (
                        <button
                          onClick={() => openWhatsApp(lead)}
                          className="btn-whatsapp"
                          title="Send WhatsApp"
                        >
                          <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                            <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
                          </svg>
                        </button>
                      )}
                      <button
                        onClick={() => openEmail(lead)}
                        className="btn-email"
                        title="Send Email"
                      >
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                          <path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/>
                        </svg>
                      </button>
                    </div>
                  </td>
                  <td>
                    <div className="actions">
                      <select
                        value={lead.status}
                        onChange={(e) => updateLeadStatus(lead.id, e.target.value)}
                        className="status-select"
                      >
                        {Object.entries(STATUS_LABELS).map(([key, label]) => (
                          <option key={key} value={key}>{label}</option>
                        ))}
                      </select>
                      <button
                        onClick={() => setSelectedLead(lead)}
                        className="btn-view"
                        title="View Details"
                      >
                        View
                      </button>
                      <button
                        onClick={() => trashLead(lead.id)}
                        className="btn-trash"
                        title="Move to Trash"
                      >
                        Trash
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Lead Detail Modal */}
      {selectedLead && (
        <div className="modal-overlay" onClick={() => setSelectedLead(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{selectedLead.business_name}</h2>
              <button onClick={() => setSelectedLead(null)}>Close</button>
            </div>
            <div className="modal-body">
              <div className="detail-grid">
                <div className="detail-item">
                  <label>Owner</label>
                  <span>{selectedLead.owner_name || '-'}</span>
                </div>
                <div className="detail-item">
                  <label>Industry</label>
                  <span>{selectedLead.industry || '-'}</span>
                </div>
                <div className="detail-item">
                  <label>Location</label>
                  <span>{selectedLead.location || '-'}</span>
                </div>
                <div className="detail-item">
                  <label>Email</label>
                  <a href={`mailto:${selectedLead.email}`}>{selectedLead.email || '-'}</a>
                </div>
                <div className="detail-item">
                  <label>Phone</label>
                  <span>{selectedLead.phone || '-'}</span>
                </div>
                <div className="detail-item">
                  <label>Website</label>
                  <a href={selectedLead.website} target="_blank" rel="noopener">
                    {selectedLead.website || '-'}
                  </a>
                </div>
                <div className="detail-item">
                  <label>Rating</label>
                  <span>{selectedLead.rating || '-'} ({selectedLead.reviews_count || 0} reviews)</span>
                </div>
                <div className="detail-item">
                  <label>Score</label>
                  <span className={`score score-${selectedLead.score >= 80 ? 'high' : selectedLead.score >= 50 ? 'medium' : 'low'}`}>
                    {selectedLead.score || '-'}
                  </span>
                </div>
                <div className="detail-item">
                  <label>Status</label>
                  <span
                    className="status-badge"
                    style={{ backgroundColor: STATUS_COLORS[selectedLead.status] }}
                  >
                    {STATUS_LABELS[selectedLead.status] || selectedLead.status}
                  </span>
                </div>
                <div className="detail-item">
                  <label>Contact Attempts</label>
                  <span>{selectedLead.contact_attempts || 0}</span>
                </div>
              </div>

              {selectedLead.notes && (
                <div className="notes-section">
                  <label>Notes</label>
                  <p>{selectedLead.notes}</p>
                </div>
              )}

              <div className="modal-actions">
                <select
                  value={selectedLead.status}
                  onChange={(e) => {
                    updateLeadStatus(selectedLead.id, e.target.value);
                    setSelectedLead({...selectedLead, status: e.target.value});
                  }}
                >
                  {Object.entries(STATUS_LABELS).map(([key, label]) => (
                    <option key={key} value={key}>{label}</option>
                  ))}
                </select>
                <button onClick={() => openWhatsApp(selectedLead)}>
                  WhatsApp
                </button>
                <button onClick={() => openEmail(selectedLead)}>
                  Send Email
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}