
#[cfg(feature = "serde")]
use serde::{Deserialize, Serialize};


#[link(name = "a1z_msgs__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_message_type_support_handle__a1z_msgs__action__MoveEndEffector_Goal() -> *const std::ffi::c_void;
}

#[link(name = "a1z_msgs__rosidl_generator_c")]
extern "C" {
    fn a1z_msgs__action__MoveEndEffector_Goal__init(msg: *mut MoveEndEffector_Goal) -> bool;
    fn a1z_msgs__action__MoveEndEffector_Goal__Sequence__init(seq: *mut rosidl_runtime_rs::Sequence<MoveEndEffector_Goal>, size: usize) -> bool;
    fn a1z_msgs__action__MoveEndEffector_Goal__Sequence__fini(seq: *mut rosidl_runtime_rs::Sequence<MoveEndEffector_Goal>);
    fn a1z_msgs__action__MoveEndEffector_Goal__Sequence__copy(in_seq: &rosidl_runtime_rs::Sequence<MoveEndEffector_Goal>, out_seq: *mut rosidl_runtime_rs::Sequence<MoveEndEffector_Goal>) -> bool;
}

// Corresponds to a1z_msgs__action__MoveEndEffector_Goal
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]


// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[repr(C)]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct MoveEndEffector_Goal {

    // This member is not documented.
    #[allow(missing_docs)]
    pub goal_pose: geometry_msgs::msg::rmw::PoseStamped,


    // This member is not documented.
    #[allow(missing_docs)]
    pub end_effector_frame: rosidl_runtime_rs::String,


    // This member is not documented.
    #[allow(missing_docs)]
    pub command_gripper: bool,


    // This member is not documented.
    #[allow(missing_docs)]
    pub gripper_opening: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub speed: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub position_tolerance_m: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub orientation_tolerance_rad: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub joint_margin_rad: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub max_joint_step_rad: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub min_target_z_m: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub max_target_z_m: f32,

}



impl Default for MoveEndEffector_Goal {
  fn default() -> Self {
    unsafe {
      let mut msg = std::mem::zeroed();
      if !a1z_msgs__action__MoveEndEffector_Goal__init(&mut msg as *mut _) {
        panic!("Call to a1z_msgs__action__MoveEndEffector_Goal__init() failed");
      }
      msg
    }
  }
}

impl rosidl_runtime_rs::SequenceAlloc for MoveEndEffector_Goal {
  fn sequence_init(seq: &mut rosidl_runtime_rs::Sequence<Self>, size: usize) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { a1z_msgs__action__MoveEndEffector_Goal__Sequence__init(seq as *mut _, size) }
  }
  fn sequence_fini(seq: &mut rosidl_runtime_rs::Sequence<Self>) {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { a1z_msgs__action__MoveEndEffector_Goal__Sequence__fini(seq as *mut _) }
  }
  fn sequence_copy(in_seq: &rosidl_runtime_rs::Sequence<Self>, out_seq: &mut rosidl_runtime_rs::Sequence<Self>) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { a1z_msgs__action__MoveEndEffector_Goal__Sequence__copy(in_seq, out_seq as *mut _) }
  }
}

impl rosidl_runtime_rs::Message for MoveEndEffector_Goal {
  type RmwMsg = Self;
  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> { msg_cow }
  fn from_rmw_message(msg: Self::RmwMsg) -> Self { msg }
}

impl rosidl_runtime_rs::RmwMessage for MoveEndEffector_Goal where Self: Sized {
  const TYPE_NAME: &'static str = "a1z_msgs/action/MoveEndEffector_Goal";
  fn get_type_support() -> *const std::ffi::c_void {
    // SAFETY: No preconditions for this function.
    unsafe { rosidl_typesupport_c__get_message_type_support_handle__a1z_msgs__action__MoveEndEffector_Goal() }
  }
}


#[link(name = "a1z_msgs__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_message_type_support_handle__a1z_msgs__action__MoveEndEffector_Result() -> *const std::ffi::c_void;
}

#[link(name = "a1z_msgs__rosidl_generator_c")]
extern "C" {
    fn a1z_msgs__action__MoveEndEffector_Result__init(msg: *mut MoveEndEffector_Result) -> bool;
    fn a1z_msgs__action__MoveEndEffector_Result__Sequence__init(seq: *mut rosidl_runtime_rs::Sequence<MoveEndEffector_Result>, size: usize) -> bool;
    fn a1z_msgs__action__MoveEndEffector_Result__Sequence__fini(seq: *mut rosidl_runtime_rs::Sequence<MoveEndEffector_Result>);
    fn a1z_msgs__action__MoveEndEffector_Result__Sequence__copy(in_seq: &rosidl_runtime_rs::Sequence<MoveEndEffector_Result>, out_seq: *mut rosidl_runtime_rs::Sequence<MoveEndEffector_Result>) -> bool;
}

// Corresponds to a1z_msgs__action__MoveEndEffector_Result
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]


// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[repr(C)]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct MoveEndEffector_Result {

    // This member is not documented.
    #[allow(missing_docs)]
    pub success: bool,


    // This member is not documented.
    #[allow(missing_docs)]
    pub status: rosidl_runtime_rs::String,


    // This member is not documented.
    #[allow(missing_docs)]
    pub failure_reason: rosidl_runtime_rs::String,


    // This member is not documented.
    #[allow(missing_docs)]
    pub final_joint_positions_rad: rosidl_runtime_rs::Sequence<f64>,


    // This member is not documented.
    #[allow(missing_docs)]
    pub final_pose: geometry_msgs::msg::rmw::PoseStamped,


    // This member is not documented.
    #[allow(missing_docs)]
    pub final_gripper_opening: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub ik_converged: bool,


    // This member is not documented.
    #[allow(missing_docs)]
    pub position_error_m: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub orientation_error_rad: f32,

}



impl Default for MoveEndEffector_Result {
  fn default() -> Self {
    unsafe {
      let mut msg = std::mem::zeroed();
      if !a1z_msgs__action__MoveEndEffector_Result__init(&mut msg as *mut _) {
        panic!("Call to a1z_msgs__action__MoveEndEffector_Result__init() failed");
      }
      msg
    }
  }
}

impl rosidl_runtime_rs::SequenceAlloc for MoveEndEffector_Result {
  fn sequence_init(seq: &mut rosidl_runtime_rs::Sequence<Self>, size: usize) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { a1z_msgs__action__MoveEndEffector_Result__Sequence__init(seq as *mut _, size) }
  }
  fn sequence_fini(seq: &mut rosidl_runtime_rs::Sequence<Self>) {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { a1z_msgs__action__MoveEndEffector_Result__Sequence__fini(seq as *mut _) }
  }
  fn sequence_copy(in_seq: &rosidl_runtime_rs::Sequence<Self>, out_seq: &mut rosidl_runtime_rs::Sequence<Self>) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { a1z_msgs__action__MoveEndEffector_Result__Sequence__copy(in_seq, out_seq as *mut _) }
  }
}

impl rosidl_runtime_rs::Message for MoveEndEffector_Result {
  type RmwMsg = Self;
  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> { msg_cow }
  fn from_rmw_message(msg: Self::RmwMsg) -> Self { msg }
}

impl rosidl_runtime_rs::RmwMessage for MoveEndEffector_Result where Self: Sized {
  const TYPE_NAME: &'static str = "a1z_msgs/action/MoveEndEffector_Result";
  fn get_type_support() -> *const std::ffi::c_void {
    // SAFETY: No preconditions for this function.
    unsafe { rosidl_typesupport_c__get_message_type_support_handle__a1z_msgs__action__MoveEndEffector_Result() }
  }
}


#[link(name = "a1z_msgs__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_message_type_support_handle__a1z_msgs__action__MoveEndEffector_Feedback() -> *const std::ffi::c_void;
}

#[link(name = "a1z_msgs__rosidl_generator_c")]
extern "C" {
    fn a1z_msgs__action__MoveEndEffector_Feedback__init(msg: *mut MoveEndEffector_Feedback) -> bool;
    fn a1z_msgs__action__MoveEndEffector_Feedback__Sequence__init(seq: *mut rosidl_runtime_rs::Sequence<MoveEndEffector_Feedback>, size: usize) -> bool;
    fn a1z_msgs__action__MoveEndEffector_Feedback__Sequence__fini(seq: *mut rosidl_runtime_rs::Sequence<MoveEndEffector_Feedback>);
    fn a1z_msgs__action__MoveEndEffector_Feedback__Sequence__copy(in_seq: &rosidl_runtime_rs::Sequence<MoveEndEffector_Feedback>, out_seq: *mut rosidl_runtime_rs::Sequence<MoveEndEffector_Feedback>) -> bool;
}

// Corresponds to a1z_msgs__action__MoveEndEffector_Feedback
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]


// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[repr(C)]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct MoveEndEffector_Feedback {

    // This member is not documented.
    #[allow(missing_docs)]
    pub stage: rosidl_runtime_rs::String,


    // This member is not documented.
    #[allow(missing_docs)]
    pub message: rosidl_runtime_rs::String,

}



impl Default for MoveEndEffector_Feedback {
  fn default() -> Self {
    unsafe {
      let mut msg = std::mem::zeroed();
      if !a1z_msgs__action__MoveEndEffector_Feedback__init(&mut msg as *mut _) {
        panic!("Call to a1z_msgs__action__MoveEndEffector_Feedback__init() failed");
      }
      msg
    }
  }
}

impl rosidl_runtime_rs::SequenceAlloc for MoveEndEffector_Feedback {
  fn sequence_init(seq: &mut rosidl_runtime_rs::Sequence<Self>, size: usize) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { a1z_msgs__action__MoveEndEffector_Feedback__Sequence__init(seq as *mut _, size) }
  }
  fn sequence_fini(seq: &mut rosidl_runtime_rs::Sequence<Self>) {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { a1z_msgs__action__MoveEndEffector_Feedback__Sequence__fini(seq as *mut _) }
  }
  fn sequence_copy(in_seq: &rosidl_runtime_rs::Sequence<Self>, out_seq: &mut rosidl_runtime_rs::Sequence<Self>) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { a1z_msgs__action__MoveEndEffector_Feedback__Sequence__copy(in_seq, out_seq as *mut _) }
  }
}

impl rosidl_runtime_rs::Message for MoveEndEffector_Feedback {
  type RmwMsg = Self;
  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> { msg_cow }
  fn from_rmw_message(msg: Self::RmwMsg) -> Self { msg }
}

impl rosidl_runtime_rs::RmwMessage for MoveEndEffector_Feedback where Self: Sized {
  const TYPE_NAME: &'static str = "a1z_msgs/action/MoveEndEffector_Feedback";
  fn get_type_support() -> *const std::ffi::c_void {
    // SAFETY: No preconditions for this function.
    unsafe { rosidl_typesupport_c__get_message_type_support_handle__a1z_msgs__action__MoveEndEffector_Feedback() }
  }
}


#[link(name = "a1z_msgs__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_message_type_support_handle__a1z_msgs__action__MoveEndEffector_FeedbackMessage() -> *const std::ffi::c_void;
}

#[link(name = "a1z_msgs__rosidl_generator_c")]
extern "C" {
    fn a1z_msgs__action__MoveEndEffector_FeedbackMessage__init(msg: *mut MoveEndEffector_FeedbackMessage) -> bool;
    fn a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence__init(seq: *mut rosidl_runtime_rs::Sequence<MoveEndEffector_FeedbackMessage>, size: usize) -> bool;
    fn a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence__fini(seq: *mut rosidl_runtime_rs::Sequence<MoveEndEffector_FeedbackMessage>);
    fn a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence__copy(in_seq: &rosidl_runtime_rs::Sequence<MoveEndEffector_FeedbackMessage>, out_seq: *mut rosidl_runtime_rs::Sequence<MoveEndEffector_FeedbackMessage>) -> bool;
}

// Corresponds to a1z_msgs__action__MoveEndEffector_FeedbackMessage
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]


// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[repr(C)]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct MoveEndEffector_FeedbackMessage {

    // This member is not documented.
    #[allow(missing_docs)]
    pub goal_id: unique_identifier_msgs::msg::rmw::UUID,


    // This member is not documented.
    #[allow(missing_docs)]
    pub feedback: super::super::action::rmw::MoveEndEffector_Feedback,

}



impl Default for MoveEndEffector_FeedbackMessage {
  fn default() -> Self {
    unsafe {
      let mut msg = std::mem::zeroed();
      if !a1z_msgs__action__MoveEndEffector_FeedbackMessage__init(&mut msg as *mut _) {
        panic!("Call to a1z_msgs__action__MoveEndEffector_FeedbackMessage__init() failed");
      }
      msg
    }
  }
}

impl rosidl_runtime_rs::SequenceAlloc for MoveEndEffector_FeedbackMessage {
  fn sequence_init(seq: &mut rosidl_runtime_rs::Sequence<Self>, size: usize) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence__init(seq as *mut _, size) }
  }
  fn sequence_fini(seq: &mut rosidl_runtime_rs::Sequence<Self>) {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence__fini(seq as *mut _) }
  }
  fn sequence_copy(in_seq: &rosidl_runtime_rs::Sequence<Self>, out_seq: &mut rosidl_runtime_rs::Sequence<Self>) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { a1z_msgs__action__MoveEndEffector_FeedbackMessage__Sequence__copy(in_seq, out_seq as *mut _) }
  }
}

impl rosidl_runtime_rs::Message for MoveEndEffector_FeedbackMessage {
  type RmwMsg = Self;
  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> { msg_cow }
  fn from_rmw_message(msg: Self::RmwMsg) -> Self { msg }
}

impl rosidl_runtime_rs::RmwMessage for MoveEndEffector_FeedbackMessage where Self: Sized {
  const TYPE_NAME: &'static str = "a1z_msgs/action/MoveEndEffector_FeedbackMessage";
  fn get_type_support() -> *const std::ffi::c_void {
    // SAFETY: No preconditions for this function.
    unsafe { rosidl_typesupport_c__get_message_type_support_handle__a1z_msgs__action__MoveEndEffector_FeedbackMessage() }
  }
}




#[link(name = "a1z_msgs__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_message_type_support_handle__a1z_msgs__action__MoveEndEffector_SendGoal_Request() -> *const std::ffi::c_void;
}

#[link(name = "a1z_msgs__rosidl_generator_c")]
extern "C" {
    fn a1z_msgs__action__MoveEndEffector_SendGoal_Request__init(msg: *mut MoveEndEffector_SendGoal_Request) -> bool;
    fn a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence__init(seq: *mut rosidl_runtime_rs::Sequence<MoveEndEffector_SendGoal_Request>, size: usize) -> bool;
    fn a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence__fini(seq: *mut rosidl_runtime_rs::Sequence<MoveEndEffector_SendGoal_Request>);
    fn a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence__copy(in_seq: &rosidl_runtime_rs::Sequence<MoveEndEffector_SendGoal_Request>, out_seq: *mut rosidl_runtime_rs::Sequence<MoveEndEffector_SendGoal_Request>) -> bool;
}

// Corresponds to a1z_msgs__action__MoveEndEffector_SendGoal_Request
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]


// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[repr(C)]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct MoveEndEffector_SendGoal_Request {

    // This member is not documented.
    #[allow(missing_docs)]
    pub goal_id: unique_identifier_msgs::msg::rmw::UUID,


    // This member is not documented.
    #[allow(missing_docs)]
    pub goal: super::super::action::rmw::MoveEndEffector_Goal,

}



impl Default for MoveEndEffector_SendGoal_Request {
  fn default() -> Self {
    unsafe {
      let mut msg = std::mem::zeroed();
      if !a1z_msgs__action__MoveEndEffector_SendGoal_Request__init(&mut msg as *mut _) {
        panic!("Call to a1z_msgs__action__MoveEndEffector_SendGoal_Request__init() failed");
      }
      msg
    }
  }
}

impl rosidl_runtime_rs::SequenceAlloc for MoveEndEffector_SendGoal_Request {
  fn sequence_init(seq: &mut rosidl_runtime_rs::Sequence<Self>, size: usize) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence__init(seq as *mut _, size) }
  }
  fn sequence_fini(seq: &mut rosidl_runtime_rs::Sequence<Self>) {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence__fini(seq as *mut _) }
  }
  fn sequence_copy(in_seq: &rosidl_runtime_rs::Sequence<Self>, out_seq: &mut rosidl_runtime_rs::Sequence<Self>) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { a1z_msgs__action__MoveEndEffector_SendGoal_Request__Sequence__copy(in_seq, out_seq as *mut _) }
  }
}

impl rosidl_runtime_rs::Message for MoveEndEffector_SendGoal_Request {
  type RmwMsg = Self;
  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> { msg_cow }
  fn from_rmw_message(msg: Self::RmwMsg) -> Self { msg }
}

impl rosidl_runtime_rs::RmwMessage for MoveEndEffector_SendGoal_Request where Self: Sized {
  const TYPE_NAME: &'static str = "a1z_msgs/action/MoveEndEffector_SendGoal_Request";
  fn get_type_support() -> *const std::ffi::c_void {
    // SAFETY: No preconditions for this function.
    unsafe { rosidl_typesupport_c__get_message_type_support_handle__a1z_msgs__action__MoveEndEffector_SendGoal_Request() }
  }
}


#[link(name = "a1z_msgs__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_message_type_support_handle__a1z_msgs__action__MoveEndEffector_SendGoal_Response() -> *const std::ffi::c_void;
}

#[link(name = "a1z_msgs__rosidl_generator_c")]
extern "C" {
    fn a1z_msgs__action__MoveEndEffector_SendGoal_Response__init(msg: *mut MoveEndEffector_SendGoal_Response) -> bool;
    fn a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence__init(seq: *mut rosidl_runtime_rs::Sequence<MoveEndEffector_SendGoal_Response>, size: usize) -> bool;
    fn a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence__fini(seq: *mut rosidl_runtime_rs::Sequence<MoveEndEffector_SendGoal_Response>);
    fn a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence__copy(in_seq: &rosidl_runtime_rs::Sequence<MoveEndEffector_SendGoal_Response>, out_seq: *mut rosidl_runtime_rs::Sequence<MoveEndEffector_SendGoal_Response>) -> bool;
}

// Corresponds to a1z_msgs__action__MoveEndEffector_SendGoal_Response
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]


// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[repr(C)]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct MoveEndEffector_SendGoal_Response {

    // This member is not documented.
    #[allow(missing_docs)]
    pub accepted: bool,


    // This member is not documented.
    #[allow(missing_docs)]
    pub stamp: builtin_interfaces::msg::rmw::Time,

}



impl Default for MoveEndEffector_SendGoal_Response {
  fn default() -> Self {
    unsafe {
      let mut msg = std::mem::zeroed();
      if !a1z_msgs__action__MoveEndEffector_SendGoal_Response__init(&mut msg as *mut _) {
        panic!("Call to a1z_msgs__action__MoveEndEffector_SendGoal_Response__init() failed");
      }
      msg
    }
  }
}

impl rosidl_runtime_rs::SequenceAlloc for MoveEndEffector_SendGoal_Response {
  fn sequence_init(seq: &mut rosidl_runtime_rs::Sequence<Self>, size: usize) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence__init(seq as *mut _, size) }
  }
  fn sequence_fini(seq: &mut rosidl_runtime_rs::Sequence<Self>) {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence__fini(seq as *mut _) }
  }
  fn sequence_copy(in_seq: &rosidl_runtime_rs::Sequence<Self>, out_seq: &mut rosidl_runtime_rs::Sequence<Self>) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { a1z_msgs__action__MoveEndEffector_SendGoal_Response__Sequence__copy(in_seq, out_seq as *mut _) }
  }
}

impl rosidl_runtime_rs::Message for MoveEndEffector_SendGoal_Response {
  type RmwMsg = Self;
  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> { msg_cow }
  fn from_rmw_message(msg: Self::RmwMsg) -> Self { msg }
}

impl rosidl_runtime_rs::RmwMessage for MoveEndEffector_SendGoal_Response where Self: Sized {
  const TYPE_NAME: &'static str = "a1z_msgs/action/MoveEndEffector_SendGoal_Response";
  fn get_type_support() -> *const std::ffi::c_void {
    // SAFETY: No preconditions for this function.
    unsafe { rosidl_typesupport_c__get_message_type_support_handle__a1z_msgs__action__MoveEndEffector_SendGoal_Response() }
  }
}


#[link(name = "a1z_msgs__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_message_type_support_handle__a1z_msgs__action__MoveEndEffector_GetResult_Request() -> *const std::ffi::c_void;
}

#[link(name = "a1z_msgs__rosidl_generator_c")]
extern "C" {
    fn a1z_msgs__action__MoveEndEffector_GetResult_Request__init(msg: *mut MoveEndEffector_GetResult_Request) -> bool;
    fn a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence__init(seq: *mut rosidl_runtime_rs::Sequence<MoveEndEffector_GetResult_Request>, size: usize) -> bool;
    fn a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence__fini(seq: *mut rosidl_runtime_rs::Sequence<MoveEndEffector_GetResult_Request>);
    fn a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence__copy(in_seq: &rosidl_runtime_rs::Sequence<MoveEndEffector_GetResult_Request>, out_seq: *mut rosidl_runtime_rs::Sequence<MoveEndEffector_GetResult_Request>) -> bool;
}

// Corresponds to a1z_msgs__action__MoveEndEffector_GetResult_Request
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]


// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[repr(C)]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct MoveEndEffector_GetResult_Request {

    // This member is not documented.
    #[allow(missing_docs)]
    pub goal_id: unique_identifier_msgs::msg::rmw::UUID,

}



impl Default for MoveEndEffector_GetResult_Request {
  fn default() -> Self {
    unsafe {
      let mut msg = std::mem::zeroed();
      if !a1z_msgs__action__MoveEndEffector_GetResult_Request__init(&mut msg as *mut _) {
        panic!("Call to a1z_msgs__action__MoveEndEffector_GetResult_Request__init() failed");
      }
      msg
    }
  }
}

impl rosidl_runtime_rs::SequenceAlloc for MoveEndEffector_GetResult_Request {
  fn sequence_init(seq: &mut rosidl_runtime_rs::Sequence<Self>, size: usize) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence__init(seq as *mut _, size) }
  }
  fn sequence_fini(seq: &mut rosidl_runtime_rs::Sequence<Self>) {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence__fini(seq as *mut _) }
  }
  fn sequence_copy(in_seq: &rosidl_runtime_rs::Sequence<Self>, out_seq: &mut rosidl_runtime_rs::Sequence<Self>) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { a1z_msgs__action__MoveEndEffector_GetResult_Request__Sequence__copy(in_seq, out_seq as *mut _) }
  }
}

impl rosidl_runtime_rs::Message for MoveEndEffector_GetResult_Request {
  type RmwMsg = Self;
  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> { msg_cow }
  fn from_rmw_message(msg: Self::RmwMsg) -> Self { msg }
}

impl rosidl_runtime_rs::RmwMessage for MoveEndEffector_GetResult_Request where Self: Sized {
  const TYPE_NAME: &'static str = "a1z_msgs/action/MoveEndEffector_GetResult_Request";
  fn get_type_support() -> *const std::ffi::c_void {
    // SAFETY: No preconditions for this function.
    unsafe { rosidl_typesupport_c__get_message_type_support_handle__a1z_msgs__action__MoveEndEffector_GetResult_Request() }
  }
}


#[link(name = "a1z_msgs__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_message_type_support_handle__a1z_msgs__action__MoveEndEffector_GetResult_Response() -> *const std::ffi::c_void;
}

#[link(name = "a1z_msgs__rosidl_generator_c")]
extern "C" {
    fn a1z_msgs__action__MoveEndEffector_GetResult_Response__init(msg: *mut MoveEndEffector_GetResult_Response) -> bool;
    fn a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence__init(seq: *mut rosidl_runtime_rs::Sequence<MoveEndEffector_GetResult_Response>, size: usize) -> bool;
    fn a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence__fini(seq: *mut rosidl_runtime_rs::Sequence<MoveEndEffector_GetResult_Response>);
    fn a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence__copy(in_seq: &rosidl_runtime_rs::Sequence<MoveEndEffector_GetResult_Response>, out_seq: *mut rosidl_runtime_rs::Sequence<MoveEndEffector_GetResult_Response>) -> bool;
}

// Corresponds to a1z_msgs__action__MoveEndEffector_GetResult_Response
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]


// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[repr(C)]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct MoveEndEffector_GetResult_Response {

    // This member is not documented.
    #[allow(missing_docs)]
    pub status: i8,


    // This member is not documented.
    #[allow(missing_docs)]
    pub result: super::super::action::rmw::MoveEndEffector_Result,

}



impl Default for MoveEndEffector_GetResult_Response {
  fn default() -> Self {
    unsafe {
      let mut msg = std::mem::zeroed();
      if !a1z_msgs__action__MoveEndEffector_GetResult_Response__init(&mut msg as *mut _) {
        panic!("Call to a1z_msgs__action__MoveEndEffector_GetResult_Response__init() failed");
      }
      msg
    }
  }
}

impl rosidl_runtime_rs::SequenceAlloc for MoveEndEffector_GetResult_Response {
  fn sequence_init(seq: &mut rosidl_runtime_rs::Sequence<Self>, size: usize) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence__init(seq as *mut _, size) }
  }
  fn sequence_fini(seq: &mut rosidl_runtime_rs::Sequence<Self>) {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence__fini(seq as *mut _) }
  }
  fn sequence_copy(in_seq: &rosidl_runtime_rs::Sequence<Self>, out_seq: &mut rosidl_runtime_rs::Sequence<Self>) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { a1z_msgs__action__MoveEndEffector_GetResult_Response__Sequence__copy(in_seq, out_seq as *mut _) }
  }
}

impl rosidl_runtime_rs::Message for MoveEndEffector_GetResult_Response {
  type RmwMsg = Self;
  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> { msg_cow }
  fn from_rmw_message(msg: Self::RmwMsg) -> Self { msg }
}

impl rosidl_runtime_rs::RmwMessage for MoveEndEffector_GetResult_Response where Self: Sized {
  const TYPE_NAME: &'static str = "a1z_msgs/action/MoveEndEffector_GetResult_Response";
  fn get_type_support() -> *const std::ffi::c_void {
    // SAFETY: No preconditions for this function.
    unsafe { rosidl_typesupport_c__get_message_type_support_handle__a1z_msgs__action__MoveEndEffector_GetResult_Response() }
  }
}






#[link(name = "a1z_msgs__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_service_type_support_handle__a1z_msgs__action__MoveEndEffector_SendGoal() -> *const std::ffi::c_void;
}

// Corresponds to a1z_msgs__action__MoveEndEffector_SendGoal
#[allow(missing_docs, non_camel_case_types)]
pub struct MoveEndEffector_SendGoal;

impl rosidl_runtime_rs::Service for MoveEndEffector_SendGoal {
    type Request = MoveEndEffector_SendGoal_Request;
    type Response = MoveEndEffector_SendGoal_Response;

    fn get_type_support() -> *const std::ffi::c_void {
        // SAFETY: No preconditions for this function.
        unsafe { rosidl_typesupport_c__get_service_type_support_handle__a1z_msgs__action__MoveEndEffector_SendGoal() }
    }
}




#[link(name = "a1z_msgs__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_service_type_support_handle__a1z_msgs__action__MoveEndEffector_GetResult() -> *const std::ffi::c_void;
}

// Corresponds to a1z_msgs__action__MoveEndEffector_GetResult
#[allow(missing_docs, non_camel_case_types)]
pub struct MoveEndEffector_GetResult;

impl rosidl_runtime_rs::Service for MoveEndEffector_GetResult {
    type Request = MoveEndEffector_GetResult_Request;
    type Response = MoveEndEffector_GetResult_Response;

    fn get_type_support() -> *const std::ffi::c_void {
        // SAFETY: No preconditions for this function.
        unsafe { rosidl_typesupport_c__get_service_type_support_handle__a1z_msgs__action__MoveEndEffector_GetResult() }
    }
}


