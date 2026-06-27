// generated from rosidl_generator_c/resource/idl__functions.h.em
// with input from a1z_msgs:action/MoveEndEffector.idl
// generated code does not contain a copyright notice

#ifndef A1Z_MSGS__ACTION__DETAIL__MOVE_END_EFFECTOR__FUNCTIONS_H_
#define A1Z_MSGS__ACTION__DETAIL__MOVE_END_EFFECTOR__FUNCTIONS_H_

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdbool.h>
#include <stdlib.h>

#include "rosidl_runtime_c/visibility_control.h"
#include "a1z_msgs/msg/rosidl_generator_c__visibility_control.h"

#include "a1z_msgs/action/detail/move_end_effector__struct.h"

/// Initialize action/MoveEndEffector message.
/**
 * If the init function is called twice for the same message without
 * calling fini inbetween previously allocated memory will be leaked.
 * \param[in,out] msg The previously allocated message pointer.
 * Fields without a default value will not be initialized by this function.
 * You might want to call memset(msg, 0, sizeof(
 * a1z_msgs__action__MoveEndEffector_Goal
 * )) before or use
 * a1z_msgs__action__MoveEndEffector_Goal__create()
 * to allocate and initialize the message.
 * \return true if initialization was successful, otherwise false
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_Goal__init(a1z_msgs__action__MoveEndEffector_Goal * msg);

/// Finalize action/MoveEndEffector message.
/**
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_Goal__fini(a1z_msgs__action__MoveEndEffector_Goal * msg);

/// Create action/MoveEndEffector message.
/**
 * It allocates the memory for the message, sets the memory to zero, and
 * calls
 * a1z_msgs__action__MoveEndEffector_Goal__init().
 * \return The pointer to the initialized message if successful,
 * otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
a1z_msgs__action__MoveEndEffector_Goal *
a1z_msgs__action__MoveEndEffector_Goal__create();

/// Destroy action/MoveEndEffector message.
/**
 * It calls
 * a1z_msgs__action__MoveEndEffector_Goal__fini()
 * and frees the memory of the message.
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_Goal__destroy(a1z_msgs__action__MoveEndEffector_Goal * msg);

/// Check for action/MoveEndEffector message equality.
/**
 * \param[in] lhs The message on the left hand size of the equality operator.
 * \param[in] rhs The message on the right hand size of the equality operator.
 * \return true if messages are equal, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_Goal__are_equal(const a1z_msgs__action__MoveEndEffector_Goal * lhs, const a1z_msgs__action__MoveEndEffector_Goal * rhs);

/// Copy a action/MoveEndEffector message.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source message pointer.
 * \param[out] output The target message pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer is null
 *   or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_Goal__copy(
  const a1z_msgs__action__MoveEndEffector_Goal * input,
  a1z_msgs__action__MoveEndEffector_Goal * output);

/// Initialize array of action/MoveEndEffector messages.
/**
 * It allocates the memory for the number of elements and calls
 * a1z_msgs__action__MoveEndEffector_Goal__init()
 * for each element of the array.
 * \param[in,out] array The allocated array pointer.
 * \param[in] size The size / capacity of the array.
 * \return true if initialization was successful, otherwise false
 * If the array pointer is valid and the size is zero it is guaranteed
 # to return true.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_Goal__Sequence__init(a1z_msgs__action__MoveEndEffector_Goal__Sequence * array, size_t size);

/// Finalize array of action/MoveEndEffector messages.
/**
 * It calls
 * a1z_msgs__action__MoveEndEffector_Goal__fini()
 * for each element of the array and frees the memory for the number of
 * elements.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_Goal__Sequence__fini(a1z_msgs__action__MoveEndEffector_Goal__Sequence * array);

/// Create array of action/MoveEndEffector messages.
/**
 * It allocates the memory for the array and calls
 * a1z_msgs__action__MoveEndEffector_Goal__Sequence__init().
 * \param[in] size The size / capacity of the array.
 * \return The pointer to the initialized array if successful, otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
a1z_msgs__action__MoveEndEffector_Goal__Sequence *
a1z_msgs__action__MoveEndEffector_Goal__Sequence__create(size_t size);

/// Destroy array of action/MoveEndEffector messages.
/**
 * It calls
 * a1z_msgs__action__MoveEndEffector_Goal__Sequence__fini()
 * on the array,
 * and frees the memory of the array.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_Goal__Sequence__destroy(a1z_msgs__action__MoveEndEffector_Goal__Sequence * array);

/// Check for action/MoveEndEffector message array equality.
/**
 * \param[in] lhs The message array on the left hand size of the equality operator.
 * \param[in] rhs The message array on the right hand size of the equality operator.
 * \return true if message arrays are equal in size and content, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_Goal__Sequence__are_equal(const a1z_msgs__action__MoveEndEffector_Goal__Sequence * lhs, const a1z_msgs__action__MoveEndEffector_Goal__Sequence * rhs);

/// Copy an array of action/MoveEndEffector messages.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source array pointer.
 * \param[out] output The target array pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer
 *   is null or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_Goal__Sequence__copy(
  const a1z_msgs__action__MoveEndEffector_Goal__Sequence * input,
  a1z_msgs__action__MoveEndEffector_Goal__Sequence * output);

/// Initialize action/MoveEndEffector message.
/**
 * If the init function is called twice for the same message without
 * calling fini inbetween previously allocated memory will be leaked.
 * \param[in,out] msg The previously allocated message pointer.
 * Fields without a default value will not be initialized by this function.
 * You might want to call memset(msg, 0, sizeof(
 * a1z_msgs__action__MoveEndEffector_Result
 * )) before or use
 * a1z_msgs__action__MoveEndEffector_Result__create()
 * to allocate and initialize the message.
 * \return true if initialization was successful, otherwise false
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_Result__init(a1z_msgs__action__MoveEndEffector_Result * msg);

/// Finalize action/MoveEndEffector message.
/**
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_Result__fini(a1z_msgs__action__MoveEndEffector_Result * msg);

/// Create action/MoveEndEffector message.
/**
 * It allocates the memory for the message, sets the memory to zero, and
 * calls
 * a1z_msgs__action__MoveEndEffector_Result__init().
 * \return The pointer to the initialized message if successful,
 * otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
a1z_msgs__action__MoveEndEffector_Result *
a1z_msgs__action__MoveEndEffector_Result__create();

/// Destroy action/MoveEndEffector message.
/**
 * It calls
 * a1z_msgs__action__MoveEndEffector_Result__fini()
 * and frees the memory of the message.
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_Result__destroy(a1z_msgs__action__MoveEndEffector_Result * msg);

/// Check for action/MoveEndEffector message equality.
/**
 * \param[in] lhs The message on the left hand size of the equality operator.
 * \param[in] rhs The message on the right hand size of the equality operator.
 * \return true if messages are equal, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_Result__are_equal(const a1z_msgs__action__MoveEndEffector_Result * lhs, const a1z_msgs__action__MoveEndEffector_Result * rhs);

/// Copy a action/MoveEndEffector message.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source message pointer.
 * \param[out] output The target message pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer is null
 *   or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_Result__copy(
  const a1z_msgs__action__MoveEndEffector_Result * input,
  a1z_msgs__action__MoveEndEffector_Result * output);

/// Initialize array of action/MoveEndEffector messages.
/**
 * It allocates the memory for the number of elements and calls
 * a1z_msgs__action__MoveEndEffector_Result__init()
 * for each element of the array.
 * \param[in,out] array The allocated array pointer.
 * \param[in] size The size / capacity of the array.
 * \return true if initialization was successful, otherwise false
 * If the array pointer is valid and the size is zero it is guaranteed
 # to return true.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_Result__Sequence__init(a1z_msgs__action__MoveEndEffector_Result__Sequence * array, size_t size);

/// Finalize array of action/MoveEndEffector messages.
/**
 * It calls
 * a1z_msgs__action__MoveEndEffector_Result__fini()
 * for each element of the array and frees the memory for the number of
 * elements.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_Result__Sequence__fini(a1z_msgs__action__MoveEndEffector_Result__Sequence * array);

/// Create array of action/MoveEndEffector messages.
/**
 * It allocates the memory for the array and calls
 * a1z_msgs__action__MoveEndEffector_Result__Sequence__init().
 * \param[in] size The size / capacity of the array.
 * \return The pointer to the initialized array if successful, otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
a1z_msgs__action__MoveEndEffector_Result__Sequence *
a1z_msgs__action__MoveEndEffector_Result__Sequence__create(size_t size);

/// Destroy array of action/MoveEndEffector messages.
/**
 * It calls
 * a1z_msgs__action__MoveEndEffector_Result__Sequence__fini()
 * on the array,
 * and frees the memory of the array.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_Result__Sequence__destroy(a1z_msgs__action__MoveEndEffector_Result__Sequence * array);

/// Check for action/MoveEndEffector message array equality.
/**
 * \param[in] lhs The message array on the left hand size of the equality operator.
 * \param[in] rhs The message array on the right hand size of the equality operator.
 * \return true if message arrays are equal in size and content, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_Result__Sequence__are_equal(const a1z_msgs__action__MoveEndEffector_Result__Sequence * lhs, const a1z_msgs__action__MoveEndEffector_Result__Sequence * rhs);

/// Copy an array of action/MoveEndEffector messages.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source array pointer.
 * \param[out] output The target array pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer
 *   is null or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_Result__Sequence__copy(
  const a1z_msgs__action__MoveEndEffector_Result__Sequence * input,
  a1z_msgs__action__MoveEndEffector_Result__Sequence * output);

/// Initialize action/MoveEndEffector message.
/**
 * If the init function is called twice for the same message without
 * calling fini inbetween previously allocated memory will be leaked.
 * \param[in,out] msg The previously allocated message pointer.
 * Fields without a default value will not be initialized by this function.
 * You might want to call memset(msg, 0, sizeof(
 * a1z_msgs__action__MoveEndEffector_Feedback
 * )) before or use
 * a1z_msgs__action__MoveEndEffector_Feedback__create()
 * to allocate and initialize the message.
 * \return true if initialization was successful, otherwise false
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_Feedback__init(a1z_msgs__action__MoveEndEffector_Feedback * msg);

/// Finalize action/MoveEndEffector message.
/**
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_Feedback__fini(a1z_msgs__action__MoveEndEffector_Feedback * msg);

/// Create action/MoveEndEffector message.
/**
 * It allocates the memory for the message, sets the memory to zero, and
 * calls
 * a1z_msgs__action__MoveEndEffector_Feedback__init().
 * \return The pointer to the initialized message if successful,
 * otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
a1z_msgs__action__MoveEndEffector_Feedback *
a1z_msgs__action__MoveEndEffector_Feedback__create();

/// Destroy action/MoveEndEffector message.
/**
 * It calls
 * a1z_msgs__action__MoveEndEffector_Feedback__fini()
 * and frees the memory of the message.
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_Feedback__destroy(a1z_msgs__action__MoveEndEffector_Feedback * msg);

/// Check for action/MoveEndEffector message equality.
/**
 * \param[in] lhs The message on the left hand size of the equality operator.
 * \param[in] rhs The message on the right hand size of the equality operator.
 * \return true if messages are equal, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_Feedback__are_equal(const a1z_msgs__action__MoveEndEffector_Feedback * lhs, const a1z_msgs__action__MoveEndEffector_Feedback * rhs);

/// Copy a action/MoveEndEffector message.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source message pointer.
 * \param[out] output The target message pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer is null
 *   or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_Feedback__copy(
  const a1z_msgs__action__MoveEndEffector_Feedback * input,
  a1z_msgs__action__MoveEndEffector_Feedback * output);

/// Initialize array of action/MoveEndEffector messages.
/**
 * It allocates the memory for the number of elements and calls
 * a1z_msgs__action__MoveEndEffector_Feedback__init()
 * for each element of the array.
 * \param[in,out] array The allocated array pointer.
 * \param[in] size The size / capacity of the array.
 * \return true if initialization was successful, otherwise false
 * If the array pointer is valid and the size is zero it is guaranteed
 # to return true.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_Feedback__Sequence__init(a1z_msgs__action__MoveEndEffector_Feedback__Sequence * array, size_t size);

/// Finalize array of action/MoveEndEffector messages.
/**
 * It calls
 * a1z_msgs__action__MoveEndEffector_Feedback__fini()
 * for each element of the array and frees the memory for the number of
 * elements.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_Feedback__Sequence__fini(a1z_msgs__action__MoveEndEffector_Feedback__Sequence * array);

/// Create array of action/MoveEndEffector messages.
/**
 * It allocates the memory for the array and calls
 * a1z_msgs__action__MoveEndEffector_Feedback__Sequence__init().
 * \param[in] size The size / capacity of the array.
 * \return The pointer to the initialized array if successful, otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
a1z_msgs__action__MoveEndEffector_Feedback__Sequence *
a1z_msgs__action__MoveEndEffector_Feedback__Sequence__create(size_t size);

/// Destroy array of action/MoveEndEffector messages.
/**
 * It calls
 * a1z_msgs__action__MoveEndEffector_Feedback__Sequence__fini()
 * on the array,
 * and frees the memory of the array.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_Feedback__Sequence__destroy(a1z_msgs__action__MoveEndEffector_Feedback__Sequence * array);

/// Check for action/MoveEndEffector message array equality.
/**
 * \param[in] lhs The message array on the left hand size of the equality operator.
 * \param[in] rhs The message array on the right hand size of the equality operator.
 * \return true if message arrays are equal in size and content, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_Feedback__Sequence__are_equal(const a1z_msgs__action__MoveEndEffector_Feedback__Sequence * lhs, const a1z_msgs__action__MoveEndEffector_Feedback__Sequence * rhs);

/// Copy an array of action/MoveEndEffector messages.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source array pointer.
 * \param[out] output The target array pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer
 *   is null or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_Feedback__Sequence__copy(
  const a1z_msgs__action__MoveEndEffector_Feedback__Sequence * input,
  a1z_msgs__action__MoveEndEffector_Feedback__Sequence * output);

/// Initialize action/MoveEndEffector message.
/**
 * If the init function is called twice for the same message without
 * calling fini inbetween previously allocated memory will be leaked.
 * \param[in,out] msg The previously allocated message pointer.
 * Fields without a default value will not be initialized by this function.
 * You might want to call memset(msg, 0, sizeof(
 * a1z_msgs__action__MoveEndEffector_SendGoal_Request
 * )) before or use
 * a1z_msgs__action__MoveEndEffector_SendGoal_Request__create()
 * to allocate and initialize the message.
 * \return true if initialization was successful, otherwise false
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_SendGoal_Request__init(a1z_msgs__action__MoveEndEffector_SendGoal_Request * msg);

/// Finalize action/MoveEndEffector message.
/**
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_SendGoal_Request__fini(a1z_msgs__action__MoveEndEffector_SendGoal_Request * msg);

/// Create action/MoveEndEffector message.
/**
 * It allocates the memory for the message, sets the memory to zero, and
 * calls
 * a1z_msgs__action__MoveEndEffector_SendGoal_Request__init().
 * \return The pointer to the initialized message if successful,
 * otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
a1z_msgs__action__MoveEndEffector_SendGoal_Request *
a1z_msgs__action__MoveEndEffector_SendGoal_Request__create();

/// Destroy action/MoveEndEffector message.
/**
 * It calls
 * a1z_msgs__action__MoveEndEffector_SendGoal_Request__fini()
 * and frees the memory of the message.
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_SendGoal_Request__destroy(a1z_msgs__action__MoveEndEffector_SendGoal_Request * msg);

/// Check for action/MoveEndEffector message equality.
/**
 * \param[in] lhs The message on the left hand size of the equality operator.
 * \param[in] rhs The message on the right hand size of the equality operator.
 * \return true if messages are equal, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_SendGoal_Request__are_equal(const a1z_msgs__action__MoveEndEffector_SendGoal_Request * lhs, const a1z_msgs__action__MoveEndEffector_SendGoal_Request * rhs);

/// Copy a action/MoveEndEffector message.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source message pointer.
 * \param[out] output The target message pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer is null
 *   or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_SendGoal_Request__copy(
  const a1z_msgs__action__MoveEndEffector_SendGoal_Request * input,
  a1z_msgs__action__MoveEndEffector_SendGoal_Request * output);

/// Initialize array of action/MoveEndEffector messages.
/**
 * It allocates the memory for the number of elements and calls
 * a1z_msgs__action__MoveEndEffector_SendGoal_Request__init()
 * for each element of the array.
 * \param[in,out] array The allocated array pointer.
 * \param[in] size The size / capacity of the array.
 * \return true if initialization was successful, otherwise false
 * If the array pointer is valid and the size is zero it is guaranteed
 # to return true.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence__init(a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence * array, size_t size);

/// Finalize array of action/MoveEndEffector messages.
/**
 * It calls
 * a1z_msgs__action__MoveEndEffector_SendGoal_Request__fini()
 * for each element of the array and frees the memory for the number of
 * elements.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence__fini(a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence * array);

/// Create array of action/MoveEndEffector messages.
/**
 * It allocates the memory for the array and calls
 * a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence__init().
 * \param[in] size The size / capacity of the array.
 * \return The pointer to the initialized array if successful, otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence *
a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence__create(size_t size);

/// Destroy array of action/MoveEndEffector messages.
/**
 * It calls
 * a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence__fini()
 * on the array,
 * and frees the memory of the array.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence__destroy(a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence * array);

/// Check for action/MoveEndEffector message array equality.
/**
 * \param[in] lhs The message array on the left hand size of the equality operator.
 * \param[in] rhs The message array on the right hand size of the equality operator.
 * \return true if message arrays are equal in size and content, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence__are_equal(const a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence * lhs, const a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence * rhs);

/// Copy an array of action/MoveEndEffector messages.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source array pointer.
 * \param[out] output The target array pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer
 *   is null or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence__copy(
  const a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence * input,
  a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence * output);

/// Initialize action/MoveEndEffector message.
/**
 * If the init function is called twice for the same message without
 * calling fini inbetween previously allocated memory will be leaked.
 * \param[in,out] msg The previously allocated message pointer.
 * Fields without a default value will not be initialized by this function.
 * You might want to call memset(msg, 0, sizeof(
 * a1z_msgs__action__MoveEndEffector_SendGoal_Response
 * )) before or use
 * a1z_msgs__action__MoveEndEffector_SendGoal_Response__create()
 * to allocate and initialize the message.
 * \return true if initialization was successful, otherwise false
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_SendGoal_Response__init(a1z_msgs__action__MoveEndEffector_SendGoal_Response * msg);

/// Finalize action/MoveEndEffector message.
/**
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_SendGoal_Response__fini(a1z_msgs__action__MoveEndEffector_SendGoal_Response * msg);

/// Create action/MoveEndEffector message.
/**
 * It allocates the memory for the message, sets the memory to zero, and
 * calls
 * a1z_msgs__action__MoveEndEffector_SendGoal_Response__init().
 * \return The pointer to the initialized message if successful,
 * otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
a1z_msgs__action__MoveEndEffector_SendGoal_Response *
a1z_msgs__action__MoveEndEffector_SendGoal_Response__create();

/// Destroy action/MoveEndEffector message.
/**
 * It calls
 * a1z_msgs__action__MoveEndEffector_SendGoal_Response__fini()
 * and frees the memory of the message.
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_SendGoal_Response__destroy(a1z_msgs__action__MoveEndEffector_SendGoal_Response * msg);

/// Check for action/MoveEndEffector message equality.
/**
 * \param[in] lhs The message on the left hand size of the equality operator.
 * \param[in] rhs The message on the right hand size of the equality operator.
 * \return true if messages are equal, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_SendGoal_Response__are_equal(const a1z_msgs__action__MoveEndEffector_SendGoal_Response * lhs, const a1z_msgs__action__MoveEndEffector_SendGoal_Response * rhs);

/// Copy a action/MoveEndEffector message.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source message pointer.
 * \param[out] output The target message pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer is null
 *   or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_SendGoal_Response__copy(
  const a1z_msgs__action__MoveEndEffector_SendGoal_Response * input,
  a1z_msgs__action__MoveEndEffector_SendGoal_Response * output);

/// Initialize array of action/MoveEndEffector messages.
/**
 * It allocates the memory for the number of elements and calls
 * a1z_msgs__action__MoveEndEffector_SendGoal_Response__init()
 * for each element of the array.
 * \param[in,out] array The allocated array pointer.
 * \param[in] size The size / capacity of the array.
 * \return true if initialization was successful, otherwise false
 * If the array pointer is valid and the size is zero it is guaranteed
 # to return true.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence__init(a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence * array, size_t size);

/// Finalize array of action/MoveEndEffector messages.
/**
 * It calls
 * a1z_msgs__action__MoveEndEffector_SendGoal_Response__fini()
 * for each element of the array and frees the memory for the number of
 * elements.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence__fini(a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence * array);

/// Create array of action/MoveEndEffector messages.
/**
 * It allocates the memory for the array and calls
 * a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence__init().
 * \param[in] size The size / capacity of the array.
 * \return The pointer to the initialized array if successful, otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence *
a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence__create(size_t size);

/// Destroy array of action/MoveEndEffector messages.
/**
 * It calls
 * a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence__fini()
 * on the array,
 * and frees the memory of the array.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence__destroy(a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence * array);

/// Check for action/MoveEndEffector message array equality.
/**
 * \param[in] lhs The message array on the left hand size of the equality operator.
 * \param[in] rhs The message array on the right hand size of the equality operator.
 * \return true if message arrays are equal in size and content, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence__are_equal(const a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence * lhs, const a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence * rhs);

/// Copy an array of action/MoveEndEffector messages.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source array pointer.
 * \param[out] output The target array pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer
 *   is null or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence__copy(
  const a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence * input,
  a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence * output);

/// Initialize action/MoveEndEffector message.
/**
 * If the init function is called twice for the same message without
 * calling fini inbetween previously allocated memory will be leaked.
 * \param[in,out] msg The previously allocated message pointer.
 * Fields without a default value will not be initialized by this function.
 * You might want to call memset(msg, 0, sizeof(
 * a1z_msgs__action__MoveEndEffector_GetResult_Request
 * )) before or use
 * a1z_msgs__action__MoveEndEffector_GetResult_Request__create()
 * to allocate and initialize the message.
 * \return true if initialization was successful, otherwise false
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_GetResult_Request__init(a1z_msgs__action__MoveEndEffector_GetResult_Request * msg);

/// Finalize action/MoveEndEffector message.
/**
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_GetResult_Request__fini(a1z_msgs__action__MoveEndEffector_GetResult_Request * msg);

/// Create action/MoveEndEffector message.
/**
 * It allocates the memory for the message, sets the memory to zero, and
 * calls
 * a1z_msgs__action__MoveEndEffector_GetResult_Request__init().
 * \return The pointer to the initialized message if successful,
 * otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
a1z_msgs__action__MoveEndEffector_GetResult_Request *
a1z_msgs__action__MoveEndEffector_GetResult_Request__create();

/// Destroy action/MoveEndEffector message.
/**
 * It calls
 * a1z_msgs__action__MoveEndEffector_GetResult_Request__fini()
 * and frees the memory of the message.
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_GetResult_Request__destroy(a1z_msgs__action__MoveEndEffector_GetResult_Request * msg);

/// Check for action/MoveEndEffector message equality.
/**
 * \param[in] lhs The message on the left hand size of the equality operator.
 * \param[in] rhs The message on the right hand size of the equality operator.
 * \return true if messages are equal, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_GetResult_Request__are_equal(const a1z_msgs__action__MoveEndEffector_GetResult_Request * lhs, const a1z_msgs__action__MoveEndEffector_GetResult_Request * rhs);

/// Copy a action/MoveEndEffector message.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source message pointer.
 * \param[out] output The target message pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer is null
 *   or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_GetResult_Request__copy(
  const a1z_msgs__action__MoveEndEffector_GetResult_Request * input,
  a1z_msgs__action__MoveEndEffector_GetResult_Request * output);

/// Initialize array of action/MoveEndEffector messages.
/**
 * It allocates the memory for the number of elements and calls
 * a1z_msgs__action__MoveEndEffector_GetResult_Request__init()
 * for each element of the array.
 * \param[in,out] array The allocated array pointer.
 * \param[in] size The size / capacity of the array.
 * \return true if initialization was successful, otherwise false
 * If the array pointer is valid and the size is zero it is guaranteed
 # to return true.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence__init(a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence * array, size_t size);

/// Finalize array of action/MoveEndEffector messages.
/**
 * It calls
 * a1z_msgs__action__MoveEndEffector_GetResult_Request__fini()
 * for each element of the array and frees the memory for the number of
 * elements.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence__fini(a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence * array);

/// Create array of action/MoveEndEffector messages.
/**
 * It allocates the memory for the array and calls
 * a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence__init().
 * \param[in] size The size / capacity of the array.
 * \return The pointer to the initialized array if successful, otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence *
a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence__create(size_t size);

/// Destroy array of action/MoveEndEffector messages.
/**
 * It calls
 * a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence__fini()
 * on the array,
 * and frees the memory of the array.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence__destroy(a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence * array);

/// Check for action/MoveEndEffector message array equality.
/**
 * \param[in] lhs The message array on the left hand size of the equality operator.
 * \param[in] rhs The message array on the right hand size of the equality operator.
 * \return true if message arrays are equal in size and content, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence__are_equal(const a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence * lhs, const a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence * rhs);

/// Copy an array of action/MoveEndEffector messages.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source array pointer.
 * \param[out] output The target array pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer
 *   is null or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence__copy(
  const a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence * input,
  a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence * output);

/// Initialize action/MoveEndEffector message.
/**
 * If the init function is called twice for the same message without
 * calling fini inbetween previously allocated memory will be leaked.
 * \param[in,out] msg The previously allocated message pointer.
 * Fields without a default value will not be initialized by this function.
 * You might want to call memset(msg, 0, sizeof(
 * a1z_msgs__action__MoveEndEffector_GetResult_Response
 * )) before or use
 * a1z_msgs__action__MoveEndEffector_GetResult_Response__create()
 * to allocate and initialize the message.
 * \return true if initialization was successful, otherwise false
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_GetResult_Response__init(a1z_msgs__action__MoveEndEffector_GetResult_Response * msg);

/// Finalize action/MoveEndEffector message.
/**
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_GetResult_Response__fini(a1z_msgs__action__MoveEndEffector_GetResult_Response * msg);

/// Create action/MoveEndEffector message.
/**
 * It allocates the memory for the message, sets the memory to zero, and
 * calls
 * a1z_msgs__action__MoveEndEffector_GetResult_Response__init().
 * \return The pointer to the initialized message if successful,
 * otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
a1z_msgs__action__MoveEndEffector_GetResult_Response *
a1z_msgs__action__MoveEndEffector_GetResult_Response__create();

/// Destroy action/MoveEndEffector message.
/**
 * It calls
 * a1z_msgs__action__MoveEndEffector_GetResult_Response__fini()
 * and frees the memory of the message.
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_GetResult_Response__destroy(a1z_msgs__action__MoveEndEffector_GetResult_Response * msg);

/// Check for action/MoveEndEffector message equality.
/**
 * \param[in] lhs The message on the left hand size of the equality operator.
 * \param[in] rhs The message on the right hand size of the equality operator.
 * \return true if messages are equal, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_GetResult_Response__are_equal(const a1z_msgs__action__MoveEndEffector_GetResult_Response * lhs, const a1z_msgs__action__MoveEndEffector_GetResult_Response * rhs);

/// Copy a action/MoveEndEffector message.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source message pointer.
 * \param[out] output The target message pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer is null
 *   or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_GetResult_Response__copy(
  const a1z_msgs__action__MoveEndEffector_GetResult_Response * input,
  a1z_msgs__action__MoveEndEffector_GetResult_Response * output);

/// Initialize array of action/MoveEndEffector messages.
/**
 * It allocates the memory for the number of elements and calls
 * a1z_msgs__action__MoveEndEffector_GetResult_Response__init()
 * for each element of the array.
 * \param[in,out] array The allocated array pointer.
 * \param[in] size The size / capacity of the array.
 * \return true if initialization was successful, otherwise false
 * If the array pointer is valid and the size is zero it is guaranteed
 # to return true.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence__init(a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence * array, size_t size);

/// Finalize array of action/MoveEndEffector messages.
/**
 * It calls
 * a1z_msgs__action__MoveEndEffector_GetResult_Response__fini()
 * for each element of the array and frees the memory for the number of
 * elements.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence__fini(a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence * array);

/// Create array of action/MoveEndEffector messages.
/**
 * It allocates the memory for the array and calls
 * a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence__init().
 * \param[in] size The size / capacity of the array.
 * \return The pointer to the initialized array if successful, otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence *
a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence__create(size_t size);

/// Destroy array of action/MoveEndEffector messages.
/**
 * It calls
 * a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence__fini()
 * on the array,
 * and frees the memory of the array.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence__destroy(a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence * array);

/// Check for action/MoveEndEffector message array equality.
/**
 * \param[in] lhs The message array on the left hand size of the equality operator.
 * \param[in] rhs The message array on the right hand size of the equality operator.
 * \return true if message arrays are equal in size and content, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence__are_equal(const a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence * lhs, const a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence * rhs);

/// Copy an array of action/MoveEndEffector messages.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source array pointer.
 * \param[out] output The target array pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer
 *   is null or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence__copy(
  const a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence * input,
  a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence * output);

/// Initialize action/MoveEndEffector message.
/**
 * If the init function is called twice for the same message without
 * calling fini inbetween previously allocated memory will be leaked.
 * \param[in,out] msg The previously allocated message pointer.
 * Fields without a default value will not be initialized by this function.
 * You might want to call memset(msg, 0, sizeof(
 * a1z_msgs__action__MoveEndEffector_FeedbackMessage
 * )) before or use
 * a1z_msgs__action__MoveEndEffector_FeedbackMessage__create()
 * to allocate and initialize the message.
 * \return true if initialization was successful, otherwise false
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_FeedbackMessage__init(a1z_msgs__action__MoveEndEffector_FeedbackMessage * msg);

/// Finalize action/MoveEndEffector message.
/**
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_FeedbackMessage__fini(a1z_msgs__action__MoveEndEffector_FeedbackMessage * msg);

/// Create action/MoveEndEffector message.
/**
 * It allocates the memory for the message, sets the memory to zero, and
 * calls
 * a1z_msgs__action__MoveEndEffector_FeedbackMessage__init().
 * \return The pointer to the initialized message if successful,
 * otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
a1z_msgs__action__MoveEndEffector_FeedbackMessage *
a1z_msgs__action__MoveEndEffector_FeedbackMessage__create();

/// Destroy action/MoveEndEffector message.
/**
 * It calls
 * a1z_msgs__action__MoveEndEffector_FeedbackMessage__fini()
 * and frees the memory of the message.
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_FeedbackMessage__destroy(a1z_msgs__action__MoveEndEffector_FeedbackMessage * msg);

/// Check for action/MoveEndEffector message equality.
/**
 * \param[in] lhs The message on the left hand size of the equality operator.
 * \param[in] rhs The message on the right hand size of the equality operator.
 * \return true if messages are equal, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_FeedbackMessage__are_equal(const a1z_msgs__action__MoveEndEffector_FeedbackMessage * lhs, const a1z_msgs__action__MoveEndEffector_FeedbackMessage * rhs);

/// Copy a action/MoveEndEffector message.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source message pointer.
 * \param[out] output The target message pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer is null
 *   or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_FeedbackMessage__copy(
  const a1z_msgs__action__MoveEndEffector_FeedbackMessage * input,
  a1z_msgs__action__MoveEndEffector_FeedbackMessage * output);

/// Initialize array of action/MoveEndEffector messages.
/**
 * It allocates the memory for the number of elements and calls
 * a1z_msgs__action__MoveEndEffector_FeedbackMessage__init()
 * for each element of the array.
 * \param[in,out] array The allocated array pointer.
 * \param[in] size The size / capacity of the array.
 * \return true if initialization was successful, otherwise false
 * If the array pointer is valid and the size is zero it is guaranteed
 # to return true.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence__init(a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence * array, size_t size);

/// Finalize array of action/MoveEndEffector messages.
/**
 * It calls
 * a1z_msgs__action__MoveEndEffector_FeedbackMessage__fini()
 * for each element of the array and frees the memory for the number of
 * elements.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence__fini(a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence * array);

/// Create array of action/MoveEndEffector messages.
/**
 * It allocates the memory for the array and calls
 * a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence__init().
 * \param[in] size The size / capacity of the array.
 * \return The pointer to the initialized array if successful, otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence *
a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence__create(size_t size);

/// Destroy array of action/MoveEndEffector messages.
/**
 * It calls
 * a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence__fini()
 * on the array,
 * and frees the memory of the array.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
void
a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence__destroy(a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence * array);

/// Check for action/MoveEndEffector message array equality.
/**
 * \param[in] lhs The message array on the left hand size of the equality operator.
 * \param[in] rhs The message array on the right hand size of the equality operator.
 * \return true if message arrays are equal in size and content, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence__are_equal(const a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence * lhs, const a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence * rhs);

/// Copy an array of action/MoveEndEffector messages.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source array pointer.
 * \param[out] output The target array pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer
 *   is null or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_a1z_msgs
bool
a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence__copy(
  const a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence * input,
  a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence * output);

#ifdef __cplusplus
}
#endif

#endif  // A1Z_MSGS__ACTION__DETAIL__MOVE_END_EFFECTOR__FUNCTIONS_H_
