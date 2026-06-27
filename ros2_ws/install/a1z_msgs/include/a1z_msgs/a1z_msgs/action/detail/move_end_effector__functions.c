// generated from rosidl_generator_c/resource/idl__functions.c.em
// with input from a1z_msgs:action/MoveEndEffector.idl
// generated code does not contain a copyright notice
#include "a1z_msgs/action/detail/move_end_effector__functions.h"

#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

#include "rcutils/allocator.h"


// Include directives for member types
// Member `goal_pose`
#include "geometry_msgs/msg/detail/pose_stamped__functions.h"
// Member `end_effector_frame`
#include "rosidl_runtime_c/string_functions.h"

bool
a1z_msgs__action__MoveEndEffector_Goal__init(a1z_msgs__action__MoveEndEffector_Goal * msg)
{
  if (!msg) {
    return false;
  }
  // goal_pose
  if (!geometry_msgs__msg__PoseStamped__init(&msg->goal_pose)) {
    a1z_msgs__action__MoveEndEffector_Goal__fini(msg);
    return false;
  }
  // end_effector_frame
  if (!rosidl_runtime_c__String__init(&msg->end_effector_frame)) {
    a1z_msgs__action__MoveEndEffector_Goal__fini(msg);
    return false;
  }
  // command_gripper
  // gripper_opening
  // speed
  // position_tolerance_m
  // orientation_tolerance_rad
  // joint_margin_rad
  // max_joint_step_rad
  // min_target_z_m
  // max_target_z_m
  return true;
}

void
a1z_msgs__action__MoveEndEffector_Goal__fini(a1z_msgs__action__MoveEndEffector_Goal * msg)
{
  if (!msg) {
    return;
  }
  // goal_pose
  geometry_msgs__msg__PoseStamped__fini(&msg->goal_pose);
  // end_effector_frame
  rosidl_runtime_c__String__fini(&msg->end_effector_frame);
  // command_gripper
  // gripper_opening
  // speed
  // position_tolerance_m
  // orientation_tolerance_rad
  // joint_margin_rad
  // max_joint_step_rad
  // min_target_z_m
  // max_target_z_m
}

bool
a1z_msgs__action__MoveEndEffector_Goal__are_equal(const a1z_msgs__action__MoveEndEffector_Goal * lhs, const a1z_msgs__action__MoveEndEffector_Goal * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // goal_pose
  if (!geometry_msgs__msg__PoseStamped__are_equal(
      &(lhs->goal_pose), &(rhs->goal_pose)))
  {
    return false;
  }
  // end_effector_frame
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->end_effector_frame), &(rhs->end_effector_frame)))
  {
    return false;
  }
  // command_gripper
  if (lhs->command_gripper != rhs->command_gripper) {
    return false;
  }
  // gripper_opening
  if (lhs->gripper_opening != rhs->gripper_opening) {
    return false;
  }
  // speed
  if (lhs->speed != rhs->speed) {
    return false;
  }
  // position_tolerance_m
  if (lhs->position_tolerance_m != rhs->position_tolerance_m) {
    return false;
  }
  // orientation_tolerance_rad
  if (lhs->orientation_tolerance_rad != rhs->orientation_tolerance_rad) {
    return false;
  }
  // joint_margin_rad
  if (lhs->joint_margin_rad != rhs->joint_margin_rad) {
    return false;
  }
  // max_joint_step_rad
  if (lhs->max_joint_step_rad != rhs->max_joint_step_rad) {
    return false;
  }
  // min_target_z_m
  if (lhs->min_target_z_m != rhs->min_target_z_m) {
    return false;
  }
  // max_target_z_m
  if (lhs->max_target_z_m != rhs->max_target_z_m) {
    return false;
  }
  return true;
}

bool
a1z_msgs__action__MoveEndEffector_Goal__copy(
  const a1z_msgs__action__MoveEndEffector_Goal * input,
  a1z_msgs__action__MoveEndEffector_Goal * output)
{
  if (!input || !output) {
    return false;
  }
  // goal_pose
  if (!geometry_msgs__msg__PoseStamped__copy(
      &(input->goal_pose), &(output->goal_pose)))
  {
    return false;
  }
  // end_effector_frame
  if (!rosidl_runtime_c__String__copy(
      &(input->end_effector_frame), &(output->end_effector_frame)))
  {
    return false;
  }
  // command_gripper
  output->command_gripper = input->command_gripper;
  // gripper_opening
  output->gripper_opening = input->gripper_opening;
  // speed
  output->speed = input->speed;
  // position_tolerance_m
  output->position_tolerance_m = input->position_tolerance_m;
  // orientation_tolerance_rad
  output->orientation_tolerance_rad = input->orientation_tolerance_rad;
  // joint_margin_rad
  output->joint_margin_rad = input->joint_margin_rad;
  // max_joint_step_rad
  output->max_joint_step_rad = input->max_joint_step_rad;
  // min_target_z_m
  output->min_target_z_m = input->min_target_z_m;
  // max_target_z_m
  output->max_target_z_m = input->max_target_z_m;
  return true;
}

a1z_msgs__action__MoveEndEffector_Goal *
a1z_msgs__action__MoveEndEffector_Goal__create()
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  a1z_msgs__action__MoveEndEffector_Goal * msg = (a1z_msgs__action__MoveEndEffector_Goal *)allocator.allocate(sizeof(a1z_msgs__action__MoveEndEffector_Goal), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(a1z_msgs__action__MoveEndEffector_Goal));
  bool success = a1z_msgs__action__MoveEndEffector_Goal__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
a1z_msgs__action__MoveEndEffector_Goal__destroy(a1z_msgs__action__MoveEndEffector_Goal * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    a1z_msgs__action__MoveEndEffector_Goal__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
a1z_msgs__action__MoveEndEffector_Goal__Sequence__init(a1z_msgs__action__MoveEndEffector_Goal__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  a1z_msgs__action__MoveEndEffector_Goal * data = NULL;

  if (size) {
    data = (a1z_msgs__action__MoveEndEffector_Goal *)allocator.zero_allocate(size, sizeof(a1z_msgs__action__MoveEndEffector_Goal), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = a1z_msgs__action__MoveEndEffector_Goal__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        a1z_msgs__action__MoveEndEffector_Goal__fini(&data[i - 1]);
      }
      allocator.deallocate(data, allocator.state);
      return false;
    }
  }
  array->data = data;
  array->size = size;
  array->capacity = size;
  return true;
}

void
a1z_msgs__action__MoveEndEffector_Goal__Sequence__fini(a1z_msgs__action__MoveEndEffector_Goal__Sequence * array)
{
  if (!array) {
    return;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();

  if (array->data) {
    // ensure that data and capacity values are consistent
    assert(array->capacity > 0);
    // finalize all array elements
    for (size_t i = 0; i < array->capacity; ++i) {
      a1z_msgs__action__MoveEndEffector_Goal__fini(&array->data[i]);
    }
    allocator.deallocate(array->data, allocator.state);
    array->data = NULL;
    array->size = 0;
    array->capacity = 0;
  } else {
    // ensure that data, size, and capacity values are consistent
    assert(0 == array->size);
    assert(0 == array->capacity);
  }
}

a1z_msgs__action__MoveEndEffector_Goal__Sequence *
a1z_msgs__action__MoveEndEffector_Goal__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  a1z_msgs__action__MoveEndEffector_Goal__Sequence * array = (a1z_msgs__action__MoveEndEffector_Goal__Sequence *)allocator.allocate(sizeof(a1z_msgs__action__MoveEndEffector_Goal__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = a1z_msgs__action__MoveEndEffector_Goal__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
a1z_msgs__action__MoveEndEffector_Goal__Sequence__destroy(a1z_msgs__action__MoveEndEffector_Goal__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    a1z_msgs__action__MoveEndEffector_Goal__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
a1z_msgs__action__MoveEndEffector_Goal__Sequence__are_equal(const a1z_msgs__action__MoveEndEffector_Goal__Sequence * lhs, const a1z_msgs__action__MoveEndEffector_Goal__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!a1z_msgs__action__MoveEndEffector_Goal__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
a1z_msgs__action__MoveEndEffector_Goal__Sequence__copy(
  const a1z_msgs__action__MoveEndEffector_Goal__Sequence * input,
  a1z_msgs__action__MoveEndEffector_Goal__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    const size_t allocation_size =
      input->size * sizeof(a1z_msgs__action__MoveEndEffector_Goal);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    a1z_msgs__action__MoveEndEffector_Goal * data =
      (a1z_msgs__action__MoveEndEffector_Goal *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!a1z_msgs__action__MoveEndEffector_Goal__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          a1z_msgs__action__MoveEndEffector_Goal__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!a1z_msgs__action__MoveEndEffector_Goal__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}


// Include directives for member types
// Member `status`
// Member `failure_reason`
// already included above
// #include "rosidl_runtime_c/string_functions.h"
// Member `final_joint_positions_rad`
#include "rosidl_runtime_c/primitives_sequence_functions.h"
// Member `final_pose`
// already included above
// #include "geometry_msgs/msg/detail/pose_stamped__functions.h"

bool
a1z_msgs__action__MoveEndEffector_Result__init(a1z_msgs__action__MoveEndEffector_Result * msg)
{
  if (!msg) {
    return false;
  }
  // success
  // status
  if (!rosidl_runtime_c__String__init(&msg->status)) {
    a1z_msgs__action__MoveEndEffector_Result__fini(msg);
    return false;
  }
  // failure_reason
  if (!rosidl_runtime_c__String__init(&msg->failure_reason)) {
    a1z_msgs__action__MoveEndEffector_Result__fini(msg);
    return false;
  }
  // final_joint_positions_rad
  if (!rosidl_runtime_c__double__Sequence__init(&msg->final_joint_positions_rad, 0)) {
    a1z_msgs__action__MoveEndEffector_Result__fini(msg);
    return false;
  }
  // final_pose
  if (!geometry_msgs__msg__PoseStamped__init(&msg->final_pose)) {
    a1z_msgs__action__MoveEndEffector_Result__fini(msg);
    return false;
  }
  // final_gripper_opening
  // ik_converged
  // position_error_m
  // orientation_error_rad
  return true;
}

void
a1z_msgs__action__MoveEndEffector_Result__fini(a1z_msgs__action__MoveEndEffector_Result * msg)
{
  if (!msg) {
    return;
  }
  // success
  // status
  rosidl_runtime_c__String__fini(&msg->status);
  // failure_reason
  rosidl_runtime_c__String__fini(&msg->failure_reason);
  // final_joint_positions_rad
  rosidl_runtime_c__double__Sequence__fini(&msg->final_joint_positions_rad);
  // final_pose
  geometry_msgs__msg__PoseStamped__fini(&msg->final_pose);
  // final_gripper_opening
  // ik_converged
  // position_error_m
  // orientation_error_rad
}

bool
a1z_msgs__action__MoveEndEffector_Result__are_equal(const a1z_msgs__action__MoveEndEffector_Result * lhs, const a1z_msgs__action__MoveEndEffector_Result * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // success
  if (lhs->success != rhs->success) {
    return false;
  }
  // status
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->status), &(rhs->status)))
  {
    return false;
  }
  // failure_reason
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->failure_reason), &(rhs->failure_reason)))
  {
    return false;
  }
  // final_joint_positions_rad
  if (!rosidl_runtime_c__double__Sequence__are_equal(
      &(lhs->final_joint_positions_rad), &(rhs->final_joint_positions_rad)))
  {
    return false;
  }
  // final_pose
  if (!geometry_msgs__msg__PoseStamped__are_equal(
      &(lhs->final_pose), &(rhs->final_pose)))
  {
    return false;
  }
  // final_gripper_opening
  if (lhs->final_gripper_opening != rhs->final_gripper_opening) {
    return false;
  }
  // ik_converged
  if (lhs->ik_converged != rhs->ik_converged) {
    return false;
  }
  // position_error_m
  if (lhs->position_error_m != rhs->position_error_m) {
    return false;
  }
  // orientation_error_rad
  if (lhs->orientation_error_rad != rhs->orientation_error_rad) {
    return false;
  }
  return true;
}

bool
a1z_msgs__action__MoveEndEffector_Result__copy(
  const a1z_msgs__action__MoveEndEffector_Result * input,
  a1z_msgs__action__MoveEndEffector_Result * output)
{
  if (!input || !output) {
    return false;
  }
  // success
  output->success = input->success;
  // status
  if (!rosidl_runtime_c__String__copy(
      &(input->status), &(output->status)))
  {
    return false;
  }
  // failure_reason
  if (!rosidl_runtime_c__String__copy(
      &(input->failure_reason), &(output->failure_reason)))
  {
    return false;
  }
  // final_joint_positions_rad
  if (!rosidl_runtime_c__double__Sequence__copy(
      &(input->final_joint_positions_rad), &(output->final_joint_positions_rad)))
  {
    return false;
  }
  // final_pose
  if (!geometry_msgs__msg__PoseStamped__copy(
      &(input->final_pose), &(output->final_pose)))
  {
    return false;
  }
  // final_gripper_opening
  output->final_gripper_opening = input->final_gripper_opening;
  // ik_converged
  output->ik_converged = input->ik_converged;
  // position_error_m
  output->position_error_m = input->position_error_m;
  // orientation_error_rad
  output->orientation_error_rad = input->orientation_error_rad;
  return true;
}

a1z_msgs__action__MoveEndEffector_Result *
a1z_msgs__action__MoveEndEffector_Result__create()
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  a1z_msgs__action__MoveEndEffector_Result * msg = (a1z_msgs__action__MoveEndEffector_Result *)allocator.allocate(sizeof(a1z_msgs__action__MoveEndEffector_Result), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(a1z_msgs__action__MoveEndEffector_Result));
  bool success = a1z_msgs__action__MoveEndEffector_Result__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
a1z_msgs__action__MoveEndEffector_Result__destroy(a1z_msgs__action__MoveEndEffector_Result * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    a1z_msgs__action__MoveEndEffector_Result__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
a1z_msgs__action__MoveEndEffector_Result__Sequence__init(a1z_msgs__action__MoveEndEffector_Result__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  a1z_msgs__action__MoveEndEffector_Result * data = NULL;

  if (size) {
    data = (a1z_msgs__action__MoveEndEffector_Result *)allocator.zero_allocate(size, sizeof(a1z_msgs__action__MoveEndEffector_Result), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = a1z_msgs__action__MoveEndEffector_Result__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        a1z_msgs__action__MoveEndEffector_Result__fini(&data[i - 1]);
      }
      allocator.deallocate(data, allocator.state);
      return false;
    }
  }
  array->data = data;
  array->size = size;
  array->capacity = size;
  return true;
}

void
a1z_msgs__action__MoveEndEffector_Result__Sequence__fini(a1z_msgs__action__MoveEndEffector_Result__Sequence * array)
{
  if (!array) {
    return;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();

  if (array->data) {
    // ensure that data and capacity values are consistent
    assert(array->capacity > 0);
    // finalize all array elements
    for (size_t i = 0; i < array->capacity; ++i) {
      a1z_msgs__action__MoveEndEffector_Result__fini(&array->data[i]);
    }
    allocator.deallocate(array->data, allocator.state);
    array->data = NULL;
    array->size = 0;
    array->capacity = 0;
  } else {
    // ensure that data, size, and capacity values are consistent
    assert(0 == array->size);
    assert(0 == array->capacity);
  }
}

a1z_msgs__action__MoveEndEffector_Result__Sequence *
a1z_msgs__action__MoveEndEffector_Result__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  a1z_msgs__action__MoveEndEffector_Result__Sequence * array = (a1z_msgs__action__MoveEndEffector_Result__Sequence *)allocator.allocate(sizeof(a1z_msgs__action__MoveEndEffector_Result__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = a1z_msgs__action__MoveEndEffector_Result__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
a1z_msgs__action__MoveEndEffector_Result__Sequence__destroy(a1z_msgs__action__MoveEndEffector_Result__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    a1z_msgs__action__MoveEndEffector_Result__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
a1z_msgs__action__MoveEndEffector_Result__Sequence__are_equal(const a1z_msgs__action__MoveEndEffector_Result__Sequence * lhs, const a1z_msgs__action__MoveEndEffector_Result__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!a1z_msgs__action__MoveEndEffector_Result__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
a1z_msgs__action__MoveEndEffector_Result__Sequence__copy(
  const a1z_msgs__action__MoveEndEffector_Result__Sequence * input,
  a1z_msgs__action__MoveEndEffector_Result__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    const size_t allocation_size =
      input->size * sizeof(a1z_msgs__action__MoveEndEffector_Result);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    a1z_msgs__action__MoveEndEffector_Result * data =
      (a1z_msgs__action__MoveEndEffector_Result *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!a1z_msgs__action__MoveEndEffector_Result__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          a1z_msgs__action__MoveEndEffector_Result__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!a1z_msgs__action__MoveEndEffector_Result__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}


// Include directives for member types
// Member `stage`
// Member `message`
// already included above
// #include "rosidl_runtime_c/string_functions.h"

bool
a1z_msgs__action__MoveEndEffector_Feedback__init(a1z_msgs__action__MoveEndEffector_Feedback * msg)
{
  if (!msg) {
    return false;
  }
  // stage
  if (!rosidl_runtime_c__String__init(&msg->stage)) {
    a1z_msgs__action__MoveEndEffector_Feedback__fini(msg);
    return false;
  }
  // message
  if (!rosidl_runtime_c__String__init(&msg->message)) {
    a1z_msgs__action__MoveEndEffector_Feedback__fini(msg);
    return false;
  }
  return true;
}

void
a1z_msgs__action__MoveEndEffector_Feedback__fini(a1z_msgs__action__MoveEndEffector_Feedback * msg)
{
  if (!msg) {
    return;
  }
  // stage
  rosidl_runtime_c__String__fini(&msg->stage);
  // message
  rosidl_runtime_c__String__fini(&msg->message);
}

bool
a1z_msgs__action__MoveEndEffector_Feedback__are_equal(const a1z_msgs__action__MoveEndEffector_Feedback * lhs, const a1z_msgs__action__MoveEndEffector_Feedback * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // stage
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->stage), &(rhs->stage)))
  {
    return false;
  }
  // message
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->message), &(rhs->message)))
  {
    return false;
  }
  return true;
}

bool
a1z_msgs__action__MoveEndEffector_Feedback__copy(
  const a1z_msgs__action__MoveEndEffector_Feedback * input,
  a1z_msgs__action__MoveEndEffector_Feedback * output)
{
  if (!input || !output) {
    return false;
  }
  // stage
  if (!rosidl_runtime_c__String__copy(
      &(input->stage), &(output->stage)))
  {
    return false;
  }
  // message
  if (!rosidl_runtime_c__String__copy(
      &(input->message), &(output->message)))
  {
    return false;
  }
  return true;
}

a1z_msgs__action__MoveEndEffector_Feedback *
a1z_msgs__action__MoveEndEffector_Feedback__create()
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  a1z_msgs__action__MoveEndEffector_Feedback * msg = (a1z_msgs__action__MoveEndEffector_Feedback *)allocator.allocate(sizeof(a1z_msgs__action__MoveEndEffector_Feedback), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(a1z_msgs__action__MoveEndEffector_Feedback));
  bool success = a1z_msgs__action__MoveEndEffector_Feedback__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
a1z_msgs__action__MoveEndEffector_Feedback__destroy(a1z_msgs__action__MoveEndEffector_Feedback * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    a1z_msgs__action__MoveEndEffector_Feedback__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
a1z_msgs__action__MoveEndEffector_Feedback__Sequence__init(a1z_msgs__action__MoveEndEffector_Feedback__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  a1z_msgs__action__MoveEndEffector_Feedback * data = NULL;

  if (size) {
    data = (a1z_msgs__action__MoveEndEffector_Feedback *)allocator.zero_allocate(size, sizeof(a1z_msgs__action__MoveEndEffector_Feedback), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = a1z_msgs__action__MoveEndEffector_Feedback__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        a1z_msgs__action__MoveEndEffector_Feedback__fini(&data[i - 1]);
      }
      allocator.deallocate(data, allocator.state);
      return false;
    }
  }
  array->data = data;
  array->size = size;
  array->capacity = size;
  return true;
}

void
a1z_msgs__action__MoveEndEffector_Feedback__Sequence__fini(a1z_msgs__action__MoveEndEffector_Feedback__Sequence * array)
{
  if (!array) {
    return;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();

  if (array->data) {
    // ensure that data and capacity values are consistent
    assert(array->capacity > 0);
    // finalize all array elements
    for (size_t i = 0; i < array->capacity; ++i) {
      a1z_msgs__action__MoveEndEffector_Feedback__fini(&array->data[i]);
    }
    allocator.deallocate(array->data, allocator.state);
    array->data = NULL;
    array->size = 0;
    array->capacity = 0;
  } else {
    // ensure that data, size, and capacity values are consistent
    assert(0 == array->size);
    assert(0 == array->capacity);
  }
}

a1z_msgs__action__MoveEndEffector_Feedback__Sequence *
a1z_msgs__action__MoveEndEffector_Feedback__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  a1z_msgs__action__MoveEndEffector_Feedback__Sequence * array = (a1z_msgs__action__MoveEndEffector_Feedback__Sequence *)allocator.allocate(sizeof(a1z_msgs__action__MoveEndEffector_Feedback__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = a1z_msgs__action__MoveEndEffector_Feedback__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
a1z_msgs__action__MoveEndEffector_Feedback__Sequence__destroy(a1z_msgs__action__MoveEndEffector_Feedback__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    a1z_msgs__action__MoveEndEffector_Feedback__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
a1z_msgs__action__MoveEndEffector_Feedback__Sequence__are_equal(const a1z_msgs__action__MoveEndEffector_Feedback__Sequence * lhs, const a1z_msgs__action__MoveEndEffector_Feedback__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!a1z_msgs__action__MoveEndEffector_Feedback__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
a1z_msgs__action__MoveEndEffector_Feedback__Sequence__copy(
  const a1z_msgs__action__MoveEndEffector_Feedback__Sequence * input,
  a1z_msgs__action__MoveEndEffector_Feedback__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    const size_t allocation_size =
      input->size * sizeof(a1z_msgs__action__MoveEndEffector_Feedback);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    a1z_msgs__action__MoveEndEffector_Feedback * data =
      (a1z_msgs__action__MoveEndEffector_Feedback *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!a1z_msgs__action__MoveEndEffector_Feedback__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          a1z_msgs__action__MoveEndEffector_Feedback__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!a1z_msgs__action__MoveEndEffector_Feedback__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}


// Include directives for member types
// Member `goal_id`
#include "unique_identifier_msgs/msg/detail/uuid__functions.h"
// Member `goal`
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__functions.h"

bool
a1z_msgs__action__MoveEndEffector_SendGoal_Request__init(a1z_msgs__action__MoveEndEffector_SendGoal_Request * msg)
{
  if (!msg) {
    return false;
  }
  // goal_id
  if (!unique_identifier_msgs__msg__UUID__init(&msg->goal_id)) {
    a1z_msgs__action__MoveEndEffector_SendGoal_Request__fini(msg);
    return false;
  }
  // goal
  if (!a1z_msgs__action__MoveEndEffector_Goal__init(&msg->goal)) {
    a1z_msgs__action__MoveEndEffector_SendGoal_Request__fini(msg);
    return false;
  }
  return true;
}

void
a1z_msgs__action__MoveEndEffector_SendGoal_Request__fini(a1z_msgs__action__MoveEndEffector_SendGoal_Request * msg)
{
  if (!msg) {
    return;
  }
  // goal_id
  unique_identifier_msgs__msg__UUID__fini(&msg->goal_id);
  // goal
  a1z_msgs__action__MoveEndEffector_Goal__fini(&msg->goal);
}

bool
a1z_msgs__action__MoveEndEffector_SendGoal_Request__are_equal(const a1z_msgs__action__MoveEndEffector_SendGoal_Request * lhs, const a1z_msgs__action__MoveEndEffector_SendGoal_Request * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // goal_id
  if (!unique_identifier_msgs__msg__UUID__are_equal(
      &(lhs->goal_id), &(rhs->goal_id)))
  {
    return false;
  }
  // goal
  if (!a1z_msgs__action__MoveEndEffector_Goal__are_equal(
      &(lhs->goal), &(rhs->goal)))
  {
    return false;
  }
  return true;
}

bool
a1z_msgs__action__MoveEndEffector_SendGoal_Request__copy(
  const a1z_msgs__action__MoveEndEffector_SendGoal_Request * input,
  a1z_msgs__action__MoveEndEffector_SendGoal_Request * output)
{
  if (!input || !output) {
    return false;
  }
  // goal_id
  if (!unique_identifier_msgs__msg__UUID__copy(
      &(input->goal_id), &(output->goal_id)))
  {
    return false;
  }
  // goal
  if (!a1z_msgs__action__MoveEndEffector_Goal__copy(
      &(input->goal), &(output->goal)))
  {
    return false;
  }
  return true;
}

a1z_msgs__action__MoveEndEffector_SendGoal_Request *
a1z_msgs__action__MoveEndEffector_SendGoal_Request__create()
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  a1z_msgs__action__MoveEndEffector_SendGoal_Request * msg = (a1z_msgs__action__MoveEndEffector_SendGoal_Request *)allocator.allocate(sizeof(a1z_msgs__action__MoveEndEffector_SendGoal_Request), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(a1z_msgs__action__MoveEndEffector_SendGoal_Request));
  bool success = a1z_msgs__action__MoveEndEffector_SendGoal_Request__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
a1z_msgs__action__MoveEndEffector_SendGoal_Request__destroy(a1z_msgs__action__MoveEndEffector_SendGoal_Request * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    a1z_msgs__action__MoveEndEffector_SendGoal_Request__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence__init(a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  a1z_msgs__action__MoveEndEffector_SendGoal_Request * data = NULL;

  if (size) {
    data = (a1z_msgs__action__MoveEndEffector_SendGoal_Request *)allocator.zero_allocate(size, sizeof(a1z_msgs__action__MoveEndEffector_SendGoal_Request), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = a1z_msgs__action__MoveEndEffector_SendGoal_Request__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        a1z_msgs__action__MoveEndEffector_SendGoal_Request__fini(&data[i - 1]);
      }
      allocator.deallocate(data, allocator.state);
      return false;
    }
  }
  array->data = data;
  array->size = size;
  array->capacity = size;
  return true;
}

void
a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence__fini(a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence * array)
{
  if (!array) {
    return;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();

  if (array->data) {
    // ensure that data and capacity values are consistent
    assert(array->capacity > 0);
    // finalize all array elements
    for (size_t i = 0; i < array->capacity; ++i) {
      a1z_msgs__action__MoveEndEffector_SendGoal_Request__fini(&array->data[i]);
    }
    allocator.deallocate(array->data, allocator.state);
    array->data = NULL;
    array->size = 0;
    array->capacity = 0;
  } else {
    // ensure that data, size, and capacity values are consistent
    assert(0 == array->size);
    assert(0 == array->capacity);
  }
}

a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence *
a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence * array = (a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence *)allocator.allocate(sizeof(a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence__destroy(a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence__are_equal(const a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence * lhs, const a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!a1z_msgs__action__MoveEndEffector_SendGoal_Request__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence__copy(
  const a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence * input,
  a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    const size_t allocation_size =
      input->size * sizeof(a1z_msgs__action__MoveEndEffector_SendGoal_Request);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    a1z_msgs__action__MoveEndEffector_SendGoal_Request * data =
      (a1z_msgs__action__MoveEndEffector_SendGoal_Request *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!a1z_msgs__action__MoveEndEffector_SendGoal_Request__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          a1z_msgs__action__MoveEndEffector_SendGoal_Request__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!a1z_msgs__action__MoveEndEffector_SendGoal_Request__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}


// Include directives for member types
// Member `stamp`
#include "builtin_interfaces/msg/detail/time__functions.h"

bool
a1z_msgs__action__MoveEndEffector_SendGoal_Response__init(a1z_msgs__action__MoveEndEffector_SendGoal_Response * msg)
{
  if (!msg) {
    return false;
  }
  // accepted
  // stamp
  if (!builtin_interfaces__msg__Time__init(&msg->stamp)) {
    a1z_msgs__action__MoveEndEffector_SendGoal_Response__fini(msg);
    return false;
  }
  return true;
}

void
a1z_msgs__action__MoveEndEffector_SendGoal_Response__fini(a1z_msgs__action__MoveEndEffector_SendGoal_Response * msg)
{
  if (!msg) {
    return;
  }
  // accepted
  // stamp
  builtin_interfaces__msg__Time__fini(&msg->stamp);
}

bool
a1z_msgs__action__MoveEndEffector_SendGoal_Response__are_equal(const a1z_msgs__action__MoveEndEffector_SendGoal_Response * lhs, const a1z_msgs__action__MoveEndEffector_SendGoal_Response * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // accepted
  if (lhs->accepted != rhs->accepted) {
    return false;
  }
  // stamp
  if (!builtin_interfaces__msg__Time__are_equal(
      &(lhs->stamp), &(rhs->stamp)))
  {
    return false;
  }
  return true;
}

bool
a1z_msgs__action__MoveEndEffector_SendGoal_Response__copy(
  const a1z_msgs__action__MoveEndEffector_SendGoal_Response * input,
  a1z_msgs__action__MoveEndEffector_SendGoal_Response * output)
{
  if (!input || !output) {
    return false;
  }
  // accepted
  output->accepted = input->accepted;
  // stamp
  if (!builtin_interfaces__msg__Time__copy(
      &(input->stamp), &(output->stamp)))
  {
    return false;
  }
  return true;
}

a1z_msgs__action__MoveEndEffector_SendGoal_Response *
a1z_msgs__action__MoveEndEffector_SendGoal_Response__create()
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  a1z_msgs__action__MoveEndEffector_SendGoal_Response * msg = (a1z_msgs__action__MoveEndEffector_SendGoal_Response *)allocator.allocate(sizeof(a1z_msgs__action__MoveEndEffector_SendGoal_Response), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(a1z_msgs__action__MoveEndEffector_SendGoal_Response));
  bool success = a1z_msgs__action__MoveEndEffector_SendGoal_Response__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
a1z_msgs__action__MoveEndEffector_SendGoal_Response__destroy(a1z_msgs__action__MoveEndEffector_SendGoal_Response * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    a1z_msgs__action__MoveEndEffector_SendGoal_Response__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence__init(a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  a1z_msgs__action__MoveEndEffector_SendGoal_Response * data = NULL;

  if (size) {
    data = (a1z_msgs__action__MoveEndEffector_SendGoal_Response *)allocator.zero_allocate(size, sizeof(a1z_msgs__action__MoveEndEffector_SendGoal_Response), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = a1z_msgs__action__MoveEndEffector_SendGoal_Response__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        a1z_msgs__action__MoveEndEffector_SendGoal_Response__fini(&data[i - 1]);
      }
      allocator.deallocate(data, allocator.state);
      return false;
    }
  }
  array->data = data;
  array->size = size;
  array->capacity = size;
  return true;
}

void
a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence__fini(a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence * array)
{
  if (!array) {
    return;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();

  if (array->data) {
    // ensure that data and capacity values are consistent
    assert(array->capacity > 0);
    // finalize all array elements
    for (size_t i = 0; i < array->capacity; ++i) {
      a1z_msgs__action__MoveEndEffector_SendGoal_Response__fini(&array->data[i]);
    }
    allocator.deallocate(array->data, allocator.state);
    array->data = NULL;
    array->size = 0;
    array->capacity = 0;
  } else {
    // ensure that data, size, and capacity values are consistent
    assert(0 == array->size);
    assert(0 == array->capacity);
  }
}

a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence *
a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence * array = (a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence *)allocator.allocate(sizeof(a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence__destroy(a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence__are_equal(const a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence * lhs, const a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!a1z_msgs__action__MoveEndEffector_SendGoal_Response__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence__copy(
  const a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence * input,
  a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    const size_t allocation_size =
      input->size * sizeof(a1z_msgs__action__MoveEndEffector_SendGoal_Response);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    a1z_msgs__action__MoveEndEffector_SendGoal_Response * data =
      (a1z_msgs__action__MoveEndEffector_SendGoal_Response *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!a1z_msgs__action__MoveEndEffector_SendGoal_Response__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          a1z_msgs__action__MoveEndEffector_SendGoal_Response__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!a1z_msgs__action__MoveEndEffector_SendGoal_Response__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}


// Include directives for member types
// Member `goal_id`
// already included above
// #include "unique_identifier_msgs/msg/detail/uuid__functions.h"

bool
a1z_msgs__action__MoveEndEffector_GetResult_Request__init(a1z_msgs__action__MoveEndEffector_GetResult_Request * msg)
{
  if (!msg) {
    return false;
  }
  // goal_id
  if (!unique_identifier_msgs__msg__UUID__init(&msg->goal_id)) {
    a1z_msgs__action__MoveEndEffector_GetResult_Request__fini(msg);
    return false;
  }
  return true;
}

void
a1z_msgs__action__MoveEndEffector_GetResult_Request__fini(a1z_msgs__action__MoveEndEffector_GetResult_Request * msg)
{
  if (!msg) {
    return;
  }
  // goal_id
  unique_identifier_msgs__msg__UUID__fini(&msg->goal_id);
}

bool
a1z_msgs__action__MoveEndEffector_GetResult_Request__are_equal(const a1z_msgs__action__MoveEndEffector_GetResult_Request * lhs, const a1z_msgs__action__MoveEndEffector_GetResult_Request * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // goal_id
  if (!unique_identifier_msgs__msg__UUID__are_equal(
      &(lhs->goal_id), &(rhs->goal_id)))
  {
    return false;
  }
  return true;
}

bool
a1z_msgs__action__MoveEndEffector_GetResult_Request__copy(
  const a1z_msgs__action__MoveEndEffector_GetResult_Request * input,
  a1z_msgs__action__MoveEndEffector_GetResult_Request * output)
{
  if (!input || !output) {
    return false;
  }
  // goal_id
  if (!unique_identifier_msgs__msg__UUID__copy(
      &(input->goal_id), &(output->goal_id)))
  {
    return false;
  }
  return true;
}

a1z_msgs__action__MoveEndEffector_GetResult_Request *
a1z_msgs__action__MoveEndEffector_GetResult_Request__create()
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  a1z_msgs__action__MoveEndEffector_GetResult_Request * msg = (a1z_msgs__action__MoveEndEffector_GetResult_Request *)allocator.allocate(sizeof(a1z_msgs__action__MoveEndEffector_GetResult_Request), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(a1z_msgs__action__MoveEndEffector_GetResult_Request));
  bool success = a1z_msgs__action__MoveEndEffector_GetResult_Request__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
a1z_msgs__action__MoveEndEffector_GetResult_Request__destroy(a1z_msgs__action__MoveEndEffector_GetResult_Request * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    a1z_msgs__action__MoveEndEffector_GetResult_Request__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence__init(a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  a1z_msgs__action__MoveEndEffector_GetResult_Request * data = NULL;

  if (size) {
    data = (a1z_msgs__action__MoveEndEffector_GetResult_Request *)allocator.zero_allocate(size, sizeof(a1z_msgs__action__MoveEndEffector_GetResult_Request), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = a1z_msgs__action__MoveEndEffector_GetResult_Request__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        a1z_msgs__action__MoveEndEffector_GetResult_Request__fini(&data[i - 1]);
      }
      allocator.deallocate(data, allocator.state);
      return false;
    }
  }
  array->data = data;
  array->size = size;
  array->capacity = size;
  return true;
}

void
a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence__fini(a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence * array)
{
  if (!array) {
    return;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();

  if (array->data) {
    // ensure that data and capacity values are consistent
    assert(array->capacity > 0);
    // finalize all array elements
    for (size_t i = 0; i < array->capacity; ++i) {
      a1z_msgs__action__MoveEndEffector_GetResult_Request__fini(&array->data[i]);
    }
    allocator.deallocate(array->data, allocator.state);
    array->data = NULL;
    array->size = 0;
    array->capacity = 0;
  } else {
    // ensure that data, size, and capacity values are consistent
    assert(0 == array->size);
    assert(0 == array->capacity);
  }
}

a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence *
a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence * array = (a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence *)allocator.allocate(sizeof(a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence__destroy(a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence__are_equal(const a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence * lhs, const a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!a1z_msgs__action__MoveEndEffector_GetResult_Request__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence__copy(
  const a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence * input,
  a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    const size_t allocation_size =
      input->size * sizeof(a1z_msgs__action__MoveEndEffector_GetResult_Request);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    a1z_msgs__action__MoveEndEffector_GetResult_Request * data =
      (a1z_msgs__action__MoveEndEffector_GetResult_Request *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!a1z_msgs__action__MoveEndEffector_GetResult_Request__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          a1z_msgs__action__MoveEndEffector_GetResult_Request__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!a1z_msgs__action__MoveEndEffector_GetResult_Request__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}


// Include directives for member types
// Member `result`
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__functions.h"

bool
a1z_msgs__action__MoveEndEffector_GetResult_Response__init(a1z_msgs__action__MoveEndEffector_GetResult_Response * msg)
{
  if (!msg) {
    return false;
  }
  // status
  // result
  if (!a1z_msgs__action__MoveEndEffector_Result__init(&msg->result)) {
    a1z_msgs__action__MoveEndEffector_GetResult_Response__fini(msg);
    return false;
  }
  return true;
}

void
a1z_msgs__action__MoveEndEffector_GetResult_Response__fini(a1z_msgs__action__MoveEndEffector_GetResult_Response * msg)
{
  if (!msg) {
    return;
  }
  // status
  // result
  a1z_msgs__action__MoveEndEffector_Result__fini(&msg->result);
}

bool
a1z_msgs__action__MoveEndEffector_GetResult_Response__are_equal(const a1z_msgs__action__MoveEndEffector_GetResult_Response * lhs, const a1z_msgs__action__MoveEndEffector_GetResult_Response * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // status
  if (lhs->status != rhs->status) {
    return false;
  }
  // result
  if (!a1z_msgs__action__MoveEndEffector_Result__are_equal(
      &(lhs->result), &(rhs->result)))
  {
    return false;
  }
  return true;
}

bool
a1z_msgs__action__MoveEndEffector_GetResult_Response__copy(
  const a1z_msgs__action__MoveEndEffector_GetResult_Response * input,
  a1z_msgs__action__MoveEndEffector_GetResult_Response * output)
{
  if (!input || !output) {
    return false;
  }
  // status
  output->status = input->status;
  // result
  if (!a1z_msgs__action__MoveEndEffector_Result__copy(
      &(input->result), &(output->result)))
  {
    return false;
  }
  return true;
}

a1z_msgs__action__MoveEndEffector_GetResult_Response *
a1z_msgs__action__MoveEndEffector_GetResult_Response__create()
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  a1z_msgs__action__MoveEndEffector_GetResult_Response * msg = (a1z_msgs__action__MoveEndEffector_GetResult_Response *)allocator.allocate(sizeof(a1z_msgs__action__MoveEndEffector_GetResult_Response), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(a1z_msgs__action__MoveEndEffector_GetResult_Response));
  bool success = a1z_msgs__action__MoveEndEffector_GetResult_Response__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
a1z_msgs__action__MoveEndEffector_GetResult_Response__destroy(a1z_msgs__action__MoveEndEffector_GetResult_Response * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    a1z_msgs__action__MoveEndEffector_GetResult_Response__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence__init(a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  a1z_msgs__action__MoveEndEffector_GetResult_Response * data = NULL;

  if (size) {
    data = (a1z_msgs__action__MoveEndEffector_GetResult_Response *)allocator.zero_allocate(size, sizeof(a1z_msgs__action__MoveEndEffector_GetResult_Response), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = a1z_msgs__action__MoveEndEffector_GetResult_Response__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        a1z_msgs__action__MoveEndEffector_GetResult_Response__fini(&data[i - 1]);
      }
      allocator.deallocate(data, allocator.state);
      return false;
    }
  }
  array->data = data;
  array->size = size;
  array->capacity = size;
  return true;
}

void
a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence__fini(a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence * array)
{
  if (!array) {
    return;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();

  if (array->data) {
    // ensure that data and capacity values are consistent
    assert(array->capacity > 0);
    // finalize all array elements
    for (size_t i = 0; i < array->capacity; ++i) {
      a1z_msgs__action__MoveEndEffector_GetResult_Response__fini(&array->data[i]);
    }
    allocator.deallocate(array->data, allocator.state);
    array->data = NULL;
    array->size = 0;
    array->capacity = 0;
  } else {
    // ensure that data, size, and capacity values are consistent
    assert(0 == array->size);
    assert(0 == array->capacity);
  }
}

a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence *
a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence * array = (a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence *)allocator.allocate(sizeof(a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence__destroy(a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence__are_equal(const a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence * lhs, const a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!a1z_msgs__action__MoveEndEffector_GetResult_Response__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence__copy(
  const a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence * input,
  a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    const size_t allocation_size =
      input->size * sizeof(a1z_msgs__action__MoveEndEffector_GetResult_Response);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    a1z_msgs__action__MoveEndEffector_GetResult_Response * data =
      (a1z_msgs__action__MoveEndEffector_GetResult_Response *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!a1z_msgs__action__MoveEndEffector_GetResult_Response__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          a1z_msgs__action__MoveEndEffector_GetResult_Response__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!a1z_msgs__action__MoveEndEffector_GetResult_Response__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}


// Include directives for member types
// Member `goal_id`
// already included above
// #include "unique_identifier_msgs/msg/detail/uuid__functions.h"
// Member `feedback`
// already included above
// #include "a1z_msgs/action/detail/move_end_effector__functions.h"

bool
a1z_msgs__action__MoveEndEffector_FeedbackMessage__init(a1z_msgs__action__MoveEndEffector_FeedbackMessage * msg)
{
  if (!msg) {
    return false;
  }
  // goal_id
  if (!unique_identifier_msgs__msg__UUID__init(&msg->goal_id)) {
    a1z_msgs__action__MoveEndEffector_FeedbackMessage__fini(msg);
    return false;
  }
  // feedback
  if (!a1z_msgs__action__MoveEndEffector_Feedback__init(&msg->feedback)) {
    a1z_msgs__action__MoveEndEffector_FeedbackMessage__fini(msg);
    return false;
  }
  return true;
}

void
a1z_msgs__action__MoveEndEffector_FeedbackMessage__fini(a1z_msgs__action__MoveEndEffector_FeedbackMessage * msg)
{
  if (!msg) {
    return;
  }
  // goal_id
  unique_identifier_msgs__msg__UUID__fini(&msg->goal_id);
  // feedback
  a1z_msgs__action__MoveEndEffector_Feedback__fini(&msg->feedback);
}

bool
a1z_msgs__action__MoveEndEffector_FeedbackMessage__are_equal(const a1z_msgs__action__MoveEndEffector_FeedbackMessage * lhs, const a1z_msgs__action__MoveEndEffector_FeedbackMessage * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // goal_id
  if (!unique_identifier_msgs__msg__UUID__are_equal(
      &(lhs->goal_id), &(rhs->goal_id)))
  {
    return false;
  }
  // feedback
  if (!a1z_msgs__action__MoveEndEffector_Feedback__are_equal(
      &(lhs->feedback), &(rhs->feedback)))
  {
    return false;
  }
  return true;
}

bool
a1z_msgs__action__MoveEndEffector_FeedbackMessage__copy(
  const a1z_msgs__action__MoveEndEffector_FeedbackMessage * input,
  a1z_msgs__action__MoveEndEffector_FeedbackMessage * output)
{
  if (!input || !output) {
    return false;
  }
  // goal_id
  if (!unique_identifier_msgs__msg__UUID__copy(
      &(input->goal_id), &(output->goal_id)))
  {
    return false;
  }
  // feedback
  if (!a1z_msgs__action__MoveEndEffector_Feedback__copy(
      &(input->feedback), &(output->feedback)))
  {
    return false;
  }
  return true;
}

a1z_msgs__action__MoveEndEffector_FeedbackMessage *
a1z_msgs__action__MoveEndEffector_FeedbackMessage__create()
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  a1z_msgs__action__MoveEndEffector_FeedbackMessage * msg = (a1z_msgs__action__MoveEndEffector_FeedbackMessage *)allocator.allocate(sizeof(a1z_msgs__action__MoveEndEffector_FeedbackMessage), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(a1z_msgs__action__MoveEndEffector_FeedbackMessage));
  bool success = a1z_msgs__action__MoveEndEffector_FeedbackMessage__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
a1z_msgs__action__MoveEndEffector_FeedbackMessage__destroy(a1z_msgs__action__MoveEndEffector_FeedbackMessage * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    a1z_msgs__action__MoveEndEffector_FeedbackMessage__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence__init(a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  a1z_msgs__action__MoveEndEffector_FeedbackMessage * data = NULL;

  if (size) {
    data = (a1z_msgs__action__MoveEndEffector_FeedbackMessage *)allocator.zero_allocate(size, sizeof(a1z_msgs__action__MoveEndEffector_FeedbackMessage), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = a1z_msgs__action__MoveEndEffector_FeedbackMessage__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        a1z_msgs__action__MoveEndEffector_FeedbackMessage__fini(&data[i - 1]);
      }
      allocator.deallocate(data, allocator.state);
      return false;
    }
  }
  array->data = data;
  array->size = size;
  array->capacity = size;
  return true;
}

void
a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence__fini(a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence * array)
{
  if (!array) {
    return;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();

  if (array->data) {
    // ensure that data and capacity values are consistent
    assert(array->capacity > 0);
    // finalize all array elements
    for (size_t i = 0; i < array->capacity; ++i) {
      a1z_msgs__action__MoveEndEffector_FeedbackMessage__fini(&array->data[i]);
    }
    allocator.deallocate(array->data, allocator.state);
    array->data = NULL;
    array->size = 0;
    array->capacity = 0;
  } else {
    // ensure that data, size, and capacity values are consistent
    assert(0 == array->size);
    assert(0 == array->capacity);
  }
}

a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence *
a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence * array = (a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence *)allocator.allocate(sizeof(a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence__destroy(a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence__are_equal(const a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence * lhs, const a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!a1z_msgs__action__MoveEndEffector_FeedbackMessage__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence__copy(
  const a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence * input,
  a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    const size_t allocation_size =
      input->size * sizeof(a1z_msgs__action__MoveEndEffector_FeedbackMessage);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    a1z_msgs__action__MoveEndEffector_FeedbackMessage * data =
      (a1z_msgs__action__MoveEndEffector_FeedbackMessage *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!a1z_msgs__action__MoveEndEffector_FeedbackMessage__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          a1z_msgs__action__MoveEndEffector_FeedbackMessage__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!a1z_msgs__action__MoveEndEffector_FeedbackMessage__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}
