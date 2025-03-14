// Copyright 2018-2025 the samurai's authors
// SPDX-License-Identifier:  BSD-3-Clause

#pragma once

#include <concepts>
#include <type_traits>

namespace samurai
{
    template <std::size_t dim, class interval_t>
    class LevelCellArray;
    // }

    // namespace samurai::experimental
    // {
    template <class Operator, class... S>
    class SetTraverser;

    template <class container_t>
    class IntervalListVisitor;

    template <class T>
    struct is_setop : std::false_type
    {
    };

    template <class... T>
    struct is_setop<SetTraverser<T...>> : std::true_type
    {
    };

    template <class T>
    constexpr bool is_setop_v{is_setop<std::decay_t<T>>::value};

    template <typename T>
    concept IsSetOp = is_setop_v<T>;

    template <typename T>
    concept IsIntervalListVisitor = std::is_base_of_v<IntervalListVisitor<typename std::decay_t<T>::container_t>, std::decay_t<T>>;

    template <typename T>
    concept IsLCA = std::same_as<LevelCellArray<T::dim, typename T::interval_t>, T>;
}
