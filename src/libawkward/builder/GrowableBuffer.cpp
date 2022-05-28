// BSD 3-Clause License; see https://github.com/scikit-hep/awkward-1.0/blob/main/LICENSE

#include "awkward/builder/ArrayBuilderOptions.h"

#include "awkward/builder/GrowableBuffer.h"
#include "awkward/kernel-utils.h"

#include <complex>
#include <cmath>
#include <cstring>

namespace awkward {
  template <typename T>
  GrowableBuffer<T>::GrowableBufferPanel::GrowableBufferPanel(size_t reserved)
      : length(0)
      , next(nullptr)
      , ptr(UniquePtr(reinterpret_cast<T*>(awkward_malloc(reserved*(int64_t)sizeof(T))))) { }

  template <typename T>
  GrowableBuffer<T>::GrowableBufferPanel::~GrowableBufferPanel() {
    for (std::unique_ptr<GrowableBufferPanel> current = std::move(next);
        current;
        current = std::move(current->next));
  }

  template <typename T>
  GrowableBuffer<T>
  GrowableBuffer<T>::empty(const ArrayBuilderOptions& options) {
    return GrowableBuffer<T>::empty(options, 0);
  }

  template <typename T>
  GrowableBuffer<T>
  GrowableBuffer<T>::empty(const ArrayBuilderOptions& options,
                           size_t minreserve) {
    size_t actual = (size_t)options.initial();
    if (actual < (size_t)minreserve) {
      actual = (size_t)minreserve;
    }
    return GrowableBuffer(options,
      UniquePtr(reinterpret_cast<T*>(awkward_malloc((int64_t)(actual*sizeof(T))))),
      0, actual, nullptr, nullptr, 0);
  }

  template <typename T>
  GrowableBuffer<T>
  GrowableBuffer<T>::full(const ArrayBuilderOptions& options,
                          T value,
                          size_t length) {
    size_t actual = (size_t)options.initial();
    if (actual < length) {
      actual = length;
    }
    UniquePtr ptr(reinterpret_cast<T*>(awkward_malloc((int64_t)(actual*sizeof(T)))));
    T* rawptr = ptr.get();
    for (size_t i = 0;  i < length;  i++) {
      rawptr[i] = value;
    }
    return GrowableBuffer<T>(options, std::move(ptr), length, actual, nullptr, nullptr, 0);
  }

  template <typename T>
  GrowableBuffer<T>
  GrowableBuffer<T>::arange(const ArrayBuilderOptions& options,
                            size_t length) {
    size_t actual = (size_t)options.initial();
    if (actual < length) {
      actual = length;
    }
    UniquePtr ptr(reinterpret_cast<T*>(awkward_malloc((int64_t)(actual*sizeof(T)))));
    T* rawptr = ptr.get();
    for (size_t i = 0;  i < length;  i++) {
      rawptr[i] = (T)i;
    }
    return GrowableBuffer(options, std::move(ptr), length, actual, nullptr, nullptr, 0);
  }

  template <typename T>
  GrowableBuffer<T>::GrowableBuffer(const ArrayBuilderOptions& options,
                                    UniquePtr ptr,
                                    size_t length,
                                    size_t reserved,
                                    GrowableBufferPanel *head,
                                    GrowableBufferPanel *tail,
                                    size_t panels)
      : options_(options)
      , ptr_(std::move(ptr))
      , length_(length)
      , reserved_(reserved)
      , head_(head)
      , tail_(tail)
      , panels_(panels) { }

  template <typename T>
  GrowableBuffer<T>::GrowableBuffer(const ArrayBuilderOptions& options)
      : GrowableBuffer(options,
                       UniquePtr(reinterpret_cast<T*>(awkward_malloc(options.initial()*(int64_t)sizeof(T)))),
                       0,
                       (size_t) options.initial(),
                       nullptr,
                       nullptr,
                       0) { }

  template <typename T>
  const typename GrowableBuffer<T>::UniquePtr&
  GrowableBuffer<T>::ptr() const {
    return ptr_;
  }

  template <typename T>
  typename GrowableBuffer<T>::UniquePtr
  GrowableBuffer<T>::get_ptr() {
    return std::move(ptr_);
  }

  template <typename T>
  size_t
  GrowableBuffer<T>::length() const {
    return length_;
  }

  template <typename T>
  void
  GrowableBuffer<T>::set_length(size_t newlength) {
    if (newlength > reserved_) {
      set_reserved(newlength);
    }
    length_ = newlength;
  }

  template <typename T>
  size_t
  GrowableBuffer<T>::reserved() const {
    return reserved_;
  }

  template <typename T>
  void
  GrowableBuffer<T>::set_reserved(size_t minreserved) {
    if (minreserved > reserved_) {
      UniquePtr ptr(reinterpret_cast<T*>(awkward_malloc((int64_t)(minreserved*sizeof(T)))));
      memcpy(ptr.get(), ptr_.get(), length_ * sizeof(T));
      ptr_ = std::move(ptr);
      reserved_ = minreserved;
    }
  }

  template <typename T>
  size_t
  GrowableBuffer<T>::panels() const {
    return panels_;
  }

  template <typename T>
  void
  GrowableBuffer<T>::fill_panel(T datum, size_t reserved) {
    if (tail_->length < reserved) {
      tail_->ptr.get()[tail_->length] = datum;
      tail_->length++;
    }
  }

  template <typename T>
  void
  GrowableBuffer<T>::add_panel(size_t reserved) {
    tail_->next = std::move(std::unique_ptr<GrowableBufferPanel>(new GrowableBufferPanel(reserved)));
    tail_ = tail_->next.get();
    panels_++;
  }

  template <typename T>
  void
  GrowableBuffer<T>::clear() {
    length_ = 0;
    reserved_ = (size_t) options_.initial();
    ptr_ = UniquePtr(reinterpret_cast<T*>(awkward_malloc(options_.initial()*(int64_t)sizeof(T))));
  }

  template <typename T>
  void
  GrowableBuffer<T>::append(T datum) {
    if (head_ == nullptr) {
      head_ =  new GrowableBufferPanel(reserved_);
      tail_ = head_;
      panels_++;
    }
    if ((length_/(panels())) == reserved_) {
      add_panel(reserved_);
    }
    fill_panel(datum, reserved_);
    length_++;
  }

  template <typename T>
  T
  GrowableBuffer<T>::getitem_at_nowrap(int64_t at) const {
    return ptr_.get()[at];
  }

  template <typename T>
  void
    GrowableBuffer<T>:: snapshot() {
      UniquePtr ptr(reinterpret_cast<T*>(awkward_malloc((int64_t)(length_*sizeof(T)))));
      GrowableBufferPanel *temp = head_;
      int64_t total_length = 0;
      while (temp != nullptr) {
        for (int64_t i = 0; i < temp->length; i++) {
          ptr.get()[total_length] = temp->ptr.get()[i];
          total_length++;
        }
        temp = temp->next.get();
      }
      ptr_ = std::move(ptr);
    }

  template class EXPORT_TEMPLATE_INST GrowableBuffer<bool>;
  template class EXPORT_TEMPLATE_INST GrowableBuffer<int8_t>;
  template class EXPORT_TEMPLATE_INST GrowableBuffer<int16_t>;
  template class EXPORT_TEMPLATE_INST GrowableBuffer<int32_t>;
  template class EXPORT_TEMPLATE_INST GrowableBuffer<int64_t>;
  template class EXPORT_TEMPLATE_INST GrowableBuffer<uint8_t>;
  template class EXPORT_TEMPLATE_INST GrowableBuffer<uint16_t>;
  template class EXPORT_TEMPLATE_INST GrowableBuffer<uint32_t>;
  template class EXPORT_TEMPLATE_INST GrowableBuffer<uint64_t>;
  template class EXPORT_TEMPLATE_INST GrowableBuffer<float>;
  template class EXPORT_TEMPLATE_INST GrowableBuffer<double>;
  template class EXPORT_TEMPLATE_INST GrowableBuffer<std::complex<float>>;
  template class EXPORT_TEMPLATE_INST GrowableBuffer<std::complex<double>>;

}
