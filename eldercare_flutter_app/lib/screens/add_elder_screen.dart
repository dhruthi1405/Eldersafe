import 'package:flutter/material.dart';
import '../models/elder.dart';
import '../services/auth_service.dart';
import '../services/firestore_service.dart';

class AddElderScreen extends StatefulWidget {
  const AddElderScreen({Key? key}) : super(key: key);

  @override
  State<AddElderScreen> createState() => _AddElderScreenState();
}

class _AddElderScreenState extends State<AddElderScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _ageController = TextEditingController();
  final _emergencyContactNameController = TextEditingController();
  final _emergencyContactPhoneController = TextEditingController();
  final _medicalConditionsController = TextEditingController();

  String _selectedGender = 'Male';
  bool _isLoading = false;

  final _authService = AuthService();
  final _firestoreService = FirestoreService();

  @override
  void dispose() {
    _nameController.dispose();
    _ageController.dispose();
    _emergencyContactNameController.dispose();
    _emergencyContactPhoneController.dispose();
    _medicalConditionsController.dispose();
    super.dispose();
  }

  Future<void> _addElder() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isLoading = true);

    try {
      final caregiverId = _authService.currentUser?.uid;
      if (caregiverId == null) throw Exception('User not authenticated');

      await _firestoreService.createElder(
        caregiverId: caregiverId,
        name: _nameController.text.trim(),
        age: int.parse(_ageController.text),
        gender: _selectedGender,
        medicalConditions: _medicalConditionsController.text.isEmpty
            ? []
            : _medicalConditionsController.text
                .split(',')
                .map((c) => c.trim())
                .toList(),
        emergencyContactName: _emergencyContactNameController.text.trim(),
        emergencyContactPhone: _emergencyContactPhoneController.text.trim(),
      );

      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Elder added successfully!')),
      );

      Navigator.of(context).pop();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: ${e.toString()}')),
      );
    } finally {
      setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Add Elder'),
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Name field
              TextFormField(
                controller: _nameController,
                decoration: InputDecoration(
                  labelText: 'Elder\'s Name',
                  hintText: 'e.g., John Smith',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                  prefixIcon: const Icon(Icons.person),
                ),
                validator: (value) {
                  if (value?.isEmpty ?? true) {
                    return 'Please enter the elder\'s name';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 16),

              // Age field
              TextFormField(
                controller: _ageController,
                decoration: InputDecoration(
                  labelText: 'Age',
                  hintText: 'e.g., 75',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                  prefixIcon: const Icon(Icons.calendar_today),
                ),
                keyboardType: TextInputType.number,
                validator: (value) {
                  if (value?.isEmpty ?? true) {
                    return 'Please enter the age';
                  }
                  if (int.tryParse(value!) == null) {
                    return 'Please enter a valid number';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 16),

              // Gender dropdown
              DropdownButtonFormField<String>(
                value: _selectedGender,
                decoration: InputDecoration(
                  labelText: 'Gender',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                  prefixIcon: const Icon(Icons.people),
                ),
                items: ['Male', 'Female', 'Other']
                    .map((gender) => DropdownMenuItem(
                          value: gender,
                          child: Text(gender),
                        ))
                    .toList(),
                onChanged: (value) {
                  if (value != null) {
                    setState(() => _selectedGender = value);
                  }
                },
              ),
              const SizedBox(height: 16),

              // Medical conditions field
              TextFormField(
                controller: _medicalConditionsController,
                decoration: InputDecoration(
                  labelText: 'Medical Conditions (Optional)',
                  hintText: 'e.g., Diabetes, Heart disease',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                  prefixIcon: const Icon(Icons.medical_services),
                ),
                maxLines: 2,
              ),
              const SizedBox(height: 16),

              // Emergency contact name
              TextFormField(
                controller: _emergencyContactNameController,
                decoration: InputDecoration(
                  labelText: 'Emergency Contact Name',
                  hintText: 'e.g., Jane Smith',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                  prefixIcon: const Icon(Icons.person_add),
                ),
                validator: (value) {
                  if (value?.isEmpty ?? true) {
                    return 'Please enter emergency contact name';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 16),

              // Emergency contact phone
              TextFormField(
                controller: _emergencyContactPhoneController,
                decoration: InputDecoration(
                  labelText: 'Emergency Contact Phone',
                  hintText: 'e.g., +1-555-1234',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                  prefixIcon: const Icon(Icons.phone),
                ),
                keyboardType: TextInputType.phone,
                validator: (value) {
                  if (value?.isEmpty ?? true) {
                    return 'Please enter emergency contact phone';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 24),

              // Submit button
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: _isLoading ? null : _addElder,
                  icon: _isLoading
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.check),
                  label: Text(_isLoading ? 'Adding...' : 'Add Elder'),
                  style: ElevatedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    backgroundColor: Colors.blue,
                    foregroundColor: Colors.white,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
