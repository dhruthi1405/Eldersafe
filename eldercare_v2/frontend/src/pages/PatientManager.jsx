import React, { useEffect, useState } from 'react';
import { Edit, Trash2 } from 'lucide-react';
import axios from 'axios';
import toast from 'react-hot-toast';

const emptyForm = {
  patient_id: '',
  full_name: '',
  date_of_birth: '',
  gender: '',
  emergency_contact: '',
  emergency_phone: '',
  medical_conditions: '',
};

const PatientManager = ({ API_BASE }) => {
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingPatientId, setEditingPatientId] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [formData, setFormData] = useState(emptyForm);

  useEffect(() => {
    loadPatients();
  }, []);

  const authHeaders = () => ({
    Authorization: `Bearer ${localStorage.getItem('token')}`,
  });

  const loadPatients = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_BASE}/patients`, {
        headers: authHeaders(),
      });
      setPatients(response.data);
    } catch (error) {
      console.error('Failed to load patients:', error);
      toast.error('Failed to load patients');
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setFormData(emptyForm);
    setEditingPatientId(null);
    setShowForm(false);
    setSubmitting(false);
  };

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);

    try {
      if (editingPatientId) {
        await axios.put(`${API_BASE}/patients/${editingPatientId}`, formData, {
          headers: authHeaders(),
        });
        toast.success('Patient updated successfully');
      } else {
        await axios.post(`${API_BASE}/patients`, formData, {
          headers: authHeaders(),
        });
        toast.success('Patient added successfully');
      }

      resetForm();
      loadPatients();
    } catch (error) {
      console.error('Failed to save patient:', error);
      toast.error(
        error?.response?.data?.detail
          || `Failed to ${editingPatientId ? 'update' : 'add'} patient`,
      );
      setSubmitting(false);
    }
  };

  const handleEdit = (patient) => {
    setEditingPatientId(patient.id);
    setFormData({
      patient_id: patient.patient_id || '',
      full_name: patient.full_name || '',
      date_of_birth: patient.date_of_birth || '',
      gender: patient.gender || '',
      emergency_contact: patient.emergency_contact || '',
      emergency_phone: patient.emergency_phone || '',
      medical_conditions: patient.medical_conditions || '',
    });
    setShowForm(true);
  };

  const handleDelete = async (patient) => {
    const confirmed = window.confirm(
      `Delete patient "${patient.full_name}" and all related sessions, predictions, and alerts?`,
    );
    if (!confirmed) return;

    try {
      await axios.delete(`${API_BASE}/patients/${patient.id}`, {
        headers: authHeaders(),
      });
      toast.success('Patient deleted successfully');

      if (editingPatientId === patient.id) {
        resetForm();
      }

      loadPatients();
    } catch (error) {
      console.error('Failed to delete patient:', error);
      toast.error(error?.response?.data?.detail || 'Failed to delete patient');
    }
  };

  if (loading) {
    return <div className="p-8 text-white">Loading...</div>;
  }

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-white text-2xl font-bold">Patient Management</h2>
        <button
          onClick={() => {
            if (showForm) {
              resetForm();
            } else {
              setShowForm(true);
            }
          }}
          className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg"
        >
          {showForm ? 'Cancel' : '+ Add Patient'}
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="bg-gray-800 rounded-lg p-6 border border-gray-700 mb-6 space-y-4"
        >
          <div className="flex items-center justify-between">
            <h3 className="text-white text-lg font-semibold">
              {editingPatientId ? 'Edit Patient' : 'Add Patient'}
            </h3>
            {editingPatientId && (
              <span className="text-sm text-blue-300">Editing existing record</span>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <input
              type="text"
              placeholder="Patient ID"
              value={formData.patient_id}
              onChange={(e) => handleChange('patient_id', e.target.value)}
              className="bg-gray-700 text-white px-4 py-2 rounded-lg"
              required
            />
            <input
              type="text"
              placeholder="Full Name"
              value={formData.full_name}
              onChange={(e) => handleChange('full_name', e.target.value)}
              className="bg-gray-700 text-white px-4 py-2 rounded-lg"
              required
            />
            <input
              type="date"
              value={formData.date_of_birth}
              onChange={(e) => handleChange('date_of_birth', e.target.value)}
              className="bg-gray-700 text-white px-4 py-2 rounded-lg"
            />
            <select
              value={formData.gender}
              onChange={(e) => handleChange('gender', e.target.value)}
              className="bg-gray-700 text-white px-4 py-2 rounded-lg"
            >
              <option value="">Gender</option>
              <option value="M">Male</option>
              <option value="F">Female</option>
              <option value="Other">Other</option>
            </select>
            <input
              type="text"
              placeholder="Emergency Contact"
              value={formData.emergency_contact}
              onChange={(e) => handleChange('emergency_contact', e.target.value)}
              className="bg-gray-700 text-white px-4 py-2 rounded-lg"
            />
            <input
              type="tel"
              placeholder="Emergency Phone"
              value={formData.emergency_phone}
              onChange={(e) => handleChange('emergency_phone', e.target.value)}
              className="bg-gray-700 text-white px-4 py-2 rounded-lg"
            />
          </div>

          <textarea
            placeholder="Medical Conditions (optional)"
            value={formData.medical_conditions}
            onChange={(e) => handleChange('medical_conditions', e.target.value)}
            className="w-full bg-gray-700 text-white px-4 py-2 rounded-lg min-h-24"
          />

          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white py-2 rounded-lg font-semibold"
          >
            {submitting
              ? (editingPatientId ? 'Updating...' : 'Saving...')
              : (editingPatientId ? 'Update Patient' : 'Add Patient')}
          </button>
        </form>
      )}

      <div className="grid gap-4">
        {patients.map((patient) => (
          <div
            key={patient.id}
            className="bg-gray-800 rounded-lg p-6 border border-gray-700 hover:border-blue-500 transition-colors"
          >
            <div className="flex justify-between items-start gap-4">
              <div>
                <h3 className="text-white font-bold text-lg">{patient.full_name}</h3>
                <p className="text-gray-400 text-sm">ID: {patient.patient_id}</p>
                <p className="text-gray-400 text-sm mt-2">DOB: {patient.date_of_birth || 'N/A'}</p>
                <p className="text-gray-400 text-sm">Gender: {patient.gender || 'N/A'}</p>
                <p className="text-gray-400 text-sm">Emergency Contact: {patient.emergency_contact || 'N/A'}</p>
                <p className="text-gray-400 text-sm">Emergency Phone: {patient.emergency_phone || 'N/A'}</p>
                {patient.medical_conditions && (
                  <p className="text-gray-400 text-sm mt-2">
                    Medical Conditions: {patient.medical_conditions}
                  </p>
                )}
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => handleEdit(patient)}
                  className="p-2 text-blue-400 hover:bg-gray-700 rounded-lg"
                  title="Edit patient"
                >
                  <Edit size={20} />
                </button>
                <button
                  onClick={() => handleDelete(patient)}
                  className="p-2 text-red-400 hover:bg-gray-700 rounded-lg"
                  title="Delete patient"
                >
                  <Trash2 size={20} />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default PatientManager;
